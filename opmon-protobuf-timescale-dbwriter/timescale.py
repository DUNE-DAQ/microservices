import logging
import queue
import threading
from dataclasses import dataclass
from urllib.parse import urlparse
import re 
from datetime import timezone

import opmonlib.opmon_entry_pb2 as opmon_schema

_MEASUREMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Index,
    MetaData,
    Table,
    Text,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy_utils import create_database, database_exists

logger = logging.getLogger(__name__)

OPMON_TABLE_PREFIX = "opmon_entries_"

@dataclass
class Entry:
    json: dict
    ms: int

class SchemaManager:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.metadata = MetaData()
        self._tables_lock = threading.Lock()

    def _table_schema(self, table_name: str) -> Table:
        return Table(
            table_name,
            self.metadata,
            Column("time", DateTime(timezone=True), nullable=False),
            Column("measurement", Text, nullable=False),
            Column("tags", JSONB, nullable=False),
            Column("fields", JSONB, nullable=False),
            Index(f"ix_{table_name}_tags_gin", "tags", postgresql_using="gin"),
            Index(f"ix_{table_name}_fields_gin", "fields", postgresql_using="gin"),
        )

    def get_or_create_table(self, measurement: str) -> Table|None:
        table_name = f"{OPMON_TABLE_PREFIX}{measurement}"

        if not _MEASUREMENT_RE.fullmatch(measurement):
            logger.error(
                "Dropping entry: measurement name %r is not a valid identifier",
                measurement,
            )
            return None

        with self._tables_lock:
            if table_name in self.metadata.tables:
                return self.metadata.tables[table_name]

            t = self._table_schema(table_name)
            with self.engine.connect() as conn:
                if not self.engine.dialect.has_table(conn, table_name):
                    t.create(conn)
                    conn.execute(
                        text(
                            f"SELECT create_hypertable('{table_name}', 'time', if_not_exists => TRUE);"
                        )
                    )
                    conn.commit()
            return t

class TimescaleWriter:
    def __init__(self, uri: str,*, create_if_missing: bool=True):
        self.engine = self._connect(uri, create_if_missing=create_if_missing)
        self.schema_manager = SchemaManager(self.engine)

    def is_healthy(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except OperationalError:
            return False
        else:
            return True

    def _connect(self, uri: str,*, create_if_missing: bool=True) -> Engine:
        db_name = urlparse(uri).path.lstrip("/")
        if not db_name:
            raise ConnectionError("No database name in URI")

        engine = create_engine(uri)
        if database_exists(engine.url):
            return engine

        if not create_if_missing:
            raise ConnectionError(f"Cannot find DB {uri}")

        create_database(engine.url)
        return engine

    def send_batch(self, batch: dict[str, list[dict]]):
        if not batch:
            return

        total_points = sum(len(v) for v in batch.values())
        logger.info(
            "Sending %s points across %s measurements", total_points, len(batch)
        )

        try:
            with self.engine.begin() as conn:
                for measurement, records in batch.items():
                    table = self.schema_manager.get_or_create_table(measurement)
                    if table is not None:                
                        conn.execute(table.insert(), records)
        except OperationalError:
            logger.exception("TimescaleDB connection error occurred")
        except SQLAlchemyError:
            logger.exception("Something went wrong: batch not sent")



class OpMonTransformer:
    def __init__(self, q: queue.Queue):
        self._q = q

    def _to_entry(self, entry: opmon_schema.OpMonEntry) -> Entry:
        data = entry.data
        fields = {}
        for key, value in data.items():
            kind = value.WhichOneof("kind")
            if kind is not None:
                fields[key] = getattr(value, kind)

        opmon_id = entry.origin
        tags = {
            "session": opmon_id.session,
            "application": opmon_id.application,
        }
        for i, s in enumerate(opmon_id.substructure):
            name = "sub" * i + "element"
            tags[name] = s
        tags.update(entry.custom_origin)

        payload = {
            "measurement": entry.measurement,
            "fields": fields,
            "tags": tags,
            "time": entry.time.ToDatetime(tzinfo=timezone.utc),
        }
        return Entry(json=payload, ms=entry.time.ToMilliseconds())

    def process_entry(self, entry: opmon_schema.OpMonEntry) -> None:
        self._q.put(self._to_entry(entry))


class BatchConsumer:
    def __init__(
        self, input_queue: queue.Queue, writer: TimescaleWriter, timeout_ms: int
    ):
        self.queue = input_queue
        self.writer = writer
        self.timeout_ms = timeout_ms

    def start(self):
        logger.info("Starting consumer thread")
        batch: dict[str, list[dict]] = {}
        batch_ms = 0

        while True:
            try:
                entry: Entry = self.queue.get(timeout=1.0)

                if batch_ms == 0:
                    batch_ms = entry.ms

                if entry.ms - batch_ms >= self.timeout_ms:
                    self.writer.send_batch(batch)
                    batch = {entry.json["measurement"]: [entry.json]}
                    batch_ms = entry.ms
                else:
                    measure = entry.json["measurement"]
                    batch.setdefault(measure, []).append(entry.json)

            except queue.Empty:
                if batch:
                    logger.debug("Queue empty, flushing batch")
                    self.writer.send_batch(batch)
                    batch = {}
                    batch_ms = 0
