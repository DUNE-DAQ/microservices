# @file dbwriter.py Writing Opmon entries into TimescaleDB
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.

import json
import logging
import queue
import socket as _socket
import threading
from dataclasses import dataclass
from functools import partial
from threading import Thread
from typing import Callable
from urllib.parse import urlparse

import click
import kafkaopmon.OpMonSubscriber as opmon_sub
import opmonlib.opmon_entry_pb2 as opmon_schema
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

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
OPMON_TABLE_PREFIX = "opmon_entries_"

logger = logging.getLogger(__name__)


def uri_to_db_name(uri: str) -> str:
    parsed_uri = urlparse(uri)
    return parsed_uri.path.lstrip("/")


@dataclass
class Entry:
    json: dict
    ms: int


class OpMonTransformer:
    @staticmethod
    def to_entry(entry: opmon_schema.OpMonEntry) -> Entry:
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
            "time": entry.time.ToDatetime(),
        }
        return Entry(json=payload, ms=entry.time.ToMilliseconds())

    @classmethod
    def process_entry(cls, entry: opmon_schema.OpMonEntry, q: queue.Queue) -> None:
        q.put(cls.to_entry(entry))


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

    def get_or_create_table(self, measurement: str) -> Table:
        table_name = f"{OPMON_TABLE_PREFIX}{measurement}"

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
    def __init__(self, uri: str, create_if_missing: bool):
        self.engine = self._connect(uri, create_if_missing)
        self.schema_manager = SchemaManager(self.engine)

    def is_healthy(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except OperationalError:
            return False

    def _connect(self, uri: str, create_if_missing: bool) -> Engine:
        db_name = uri_to_db_name(uri)
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
                    conn.execute(table.insert(), records)
        except OperationalError:
            logger.exception("TimescaleDB connection error occurred")
        except SQLAlchemyError:
            logger.exception("Something went wrong: batch not sent")


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


class HealthServer:
    def __init__(self, port: int, health_check: Callable[[], bool]):
        self.port = port
        self._health_check = health_check
        self._sock: _socket.socket | None = None

    def start(self) -> None:
        self._sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        self._sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", self.port))
        self._sock.listen(10)
        Thread(target=self._accept_loop, daemon=True).start()
        logger.info("Health server started on port %d", self.port)

    def stop(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while True:
            try:
                conn, _ = self._sock.accept()
                Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except OSError:
                break

    def _handle_client(self, conn: _socket.socket) -> None:
        try:
            data = b""
            conn.settimeout(5)
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk

            if b"GET /ready" in data:
                healthy = self._health_check()
                code, phrase = (200, "OK") if healthy else (503, "Service Unavailable")
                body = json.dumps({
                    "status": "ready" if healthy else "not ready",
                    "timescaledb": "healthy" if healthy else "unreachable",
                }).encode()
            elif b"GET /live" in data:
                code, phrase = 200, "OK"
                body = json.dumps({"status": "live"}).encode()
            else:
                code, phrase = 404, "Not Found"
                body = b"Not Found"

            response = (
                f"HTTP/1.0 {code} {phrase}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n\r\n"
            ).encode() + body
            conn.sendall(response)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--subscriber-bootstrap",
    type=click.STRING,
    default="monkafka.cern.ch:30092",
    help="boostrap server and port of the OpMonSubscriber",
)
@click.option(
    "--subscriber-group",
    type=click.STRING,
    default=None,
    help="group ID of the OpMonSubscriber",
)
@click.option(
    "--subscriber-timeout",
    type=click.INT,
    default=500,
    help="timeout in ms used in the OpMonSubscriber",
)
@click.option(
    "--subscriber-topic",
    type=click.STRING,
    multiple=True,
    default=["opmon_stream"],
    help='The system will add the "monitoring." prefix',
)
@click.option(
    "--timescaledb_uri",
    type=click.STRING,
    default="postgres://localhost:8086/test_timescaledb",
    help="URI of the timescaleDB server (e.g., postgres]://user:pass@host:port/dbname)",
)
@click.option(
    "--timescaledb_create",
    type=click.BOOL,
    default=True,
    help="Creates the timescaledb if it does not exists",
)
@click.option(
    "--timescaledb_timeout",
    type=click.INT,
    default=500,
    help="Size in ms of the batches sent to timescale",
)
@click.option("--debug", type=click.BOOL, default=True, help="Set debug print levels")
@click.option(
    "--health-port",
    type=click.INT,
    default=None,
    help="Port for HTTP health endpoint (if not set, no health endpoint)",
)
def cli(
    subscriber_bootstrap,
    subscriber_group,
    subscriber_timeout,
    subscriber_topic,
    timescaledb_uri,
    timescaledb_create,
    timescaledb_timeout,
    debug,
    health_port,
):
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    writer = TimescaleWriter(timescaledb_uri, timescaledb_create)

    if health_port is not None:
        HealthServer(health_port, health_check=writer.is_healthy).start()

    q = queue.Queue()
    sub = opmon_sub.OpMonSubscriber(
        bootstrap=subscriber_bootstrap,
        topics=subscriber_topic,
        group_id=subscriber_group,
        timeout_ms=subscriber_timeout,
    )
    sub.add_callback(
        name="to_timescale_db",
        function=partial(OpMonTransformer.process_entry, q=q),
    )

    consumer = BatchConsumer(q, writer, timescaledb_timeout)
    threading.Thread(target=consumer.start, daemon=True).start()

    sub.start()


if __name__ == "__main__":
    cli()