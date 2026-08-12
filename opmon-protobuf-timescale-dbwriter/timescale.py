"""TimescaleDB writer and batch consumer for OpMon entries.

This module handles the persistence of monitoring entries from Kafka into
TimescaleDB, with automatic schema creation, batching, and error handling.
"""

import logging
import queue
import re
import threading
from dataclasses import dataclass
from datetime import timezone
from urllib.parse import urlparse

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

logger = logging.getLogger(__name__)

_MEASUREMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
OPMON_TABLE_PREFIX = "opmon_entries_"

# Type alias for batch data structure: {measurement_name: [entry_dicts]}
BatchData = dict[str, list[dict]]


@dataclass
class Entry:
    """A transformed OpMon entry ready for batch insertion.

    Attributes:
        json: Dictionary containing 'measurement', 'fields', 'tags', and 'time'.
        ms: Millisecond timestamp for batch timeout logic.
    """

    json: dict
    ms: int


class SchemaManager:
    """Manages TimescaleDB table schemas for measurements.

    Creates measurement tables on-demand with hypertable configuration
    and thread-safe table metadata caching.
    """

    def __init__(self, engine: Engine) -> None:
        """Initialize schema manager.

        Args:
            engine: SQLAlchemy Engine connected to TimescaleDB.
        """
        self.engine = engine
        self.metadata = MetaData()
        self._tables_lock = threading.Lock()

    def _table_schema(self, table_name: str) -> Table:
        """Create table schema definition.

        Args:
            table_name: Name of the table to create.

        Returns:
            SQLAlchemy Table object with proper columns and indexes.
        """
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
        """Get or create a table for the given measurement.

        Args:
            measurement: Measurement name (pre-validated as SQL identifier).

        Returns:
            SQLAlchemy Table object.

        Note:
            Measurement names must be validated by caller (OpMonTransformer).
        """
        table_name = f"{OPMON_TABLE_PREFIX}{measurement}"

        with self._tables_lock:
            if table_name in self.metadata.tables:
                return self.metadata.tables[table_name]

            table = self._table_schema(table_name)
            with self.engine.begin() as conn:
                if not self.engine.dialect.has_table(conn, table_name):
                    table.create(conn)
                    conn.execute(
                        text(
                            f"SELECT create_hypertable('{table_name}', 'time', "
                            "if_not_exists => TRUE);"
                        )
                    )
            return table


class TimescaleWriter:
    """Manages database connections and batch writes to TimescaleDB."""

    def __init__(self, uri: str, *, create_if_missing: bool = True) -> None:
        """Initialize TimescaleDB writer.

        Args:
            uri: PostgreSQL connection URI.
            create_if_missing: If True, create database if it doesn't exist.

        Raises:
            ConnectionError: If database doesn't exist and create_if_missing is False,
                or if URI has no database name.
        """
        self.engine = self._connect(uri, create_if_missing=create_if_missing)
        self.schema_manager = SchemaManager(self.engine)

    def is_healthy(self) -> bool:
        """Check if database connection is healthy.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except OperationalError:
            return False
        else:
            return True

    def _connect(self, uri: str, *, create_if_missing: bool = True) -> Engine:
        """Establish connection to TimescaleDB.

        Args:
            uri: PostgreSQL connection URI.
            create_if_missing: If True, create database if it doesn't exist.

        Returns:
            SQLAlchemy Engine instance.

        Raises:
            ConnectionError: If database doesn't exist and create_if_missing is False,
                or if URI has no database name.
        """
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

    def send_batch(self, batch: BatchData) -> None:
        """Send a batch of entries to TimescaleDB.

        Args:
            batch: Dictionary mapping measurement names to lists of entry dicts.
        """
        if not batch:
            return

        total_points = sum(len(v) for v in batch.values())
        logger.info(
            "Sending %d points across %d measurements", total_points, len(batch)
        )

        try:
            with self.engine.begin() as conn:
                for measurement, records in batch.items():
                    table = self.schema_manager.get_or_create_table(measurement)
                    conn.execute(table.insert(), records)
                    logger.debug(
                        "Inserted %d records into measurement %r",
                        len(records),
                        measurement,
                    )
        except OperationalError:
            logger.exception("TimescaleDB connection error occurred")
        except SQLAlchemyError:
            logger.exception("Failed to write batch to TimescaleDB")


class OpMonTransformer:
    """Transforms raw OpMon protobuf entries into queue-ready Entry objects."""

    def __init__(self, q: queue.Queue[Entry]) -> None:
        """Initialize transformer with output queue.

        Args:
            q: Queue to place transformed entries into.
        """
        self._q = q

    def _to_entry(self, entry: opmon_schema.OpMonEntry) -> Entry:
        """Transform protobuf entry to internal Entry format.

        Args:
            entry: OpMon protobuf entry from Kafka.

        Returns:
            Transformed Entry ready for batch insertion.
        """
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
        """Process and queue a single OpMon entry.

        Args:
            entry: OpMon protobuf entry from Kafka.

        Logs errors if transformation fails but does not propagate exceptions.
        """
        # Validate measurement name early to avoid queue pollution
        if not _MEASUREMENT_RE.fullmatch(entry.measurement):
            logger.warning(
                "Dropping entry: invalid measurement name %r from %r",
                entry.measurement,
                entry.origin.application,
            )
            return

        try:
            self._q.put(self._to_entry(entry))
            logger.debug(
                "Queued entry from %r (measurement: %r)",
                entry.origin.application,
                entry.measurement,
            )
        except (AttributeError, TypeError, ValueError):
            logger.exception(
                "Failed to transform entry from %r",
                entry.origin.application,
            )
        except queue.Full:
            logger.exception(
                "Entry queue full, dropping entry from %r",
                entry.origin.application,
            )


class BatchConsumer:
    """Batches entries and writes them to TimescaleDB with timeout-based flushing."""

    def __init__(
        self, input_queue: queue.Queue[Entry], writer: TimescaleWriter, timeout_ms: int
    ) -> None:
        """Initialize batch consumer.

        Args:
            input_queue: Queue of Entry objects to consume.
            writer: TimescaleWriter instance for batch writes.
            timeout_ms: Maximum millisecond age of a batch before forced flush.
        """
        self.queue = input_queue
        self.writer = writer
        self.timeout_ms = timeout_ms

    def _reset_batch(self) -> tuple[BatchData, int]:
        """Reset batch and batch_ms to empty state.

        Returns:
            Tuple of (empty_batch, reset_ms).
        """
        return {}, 0

    def start(self) -> None:
        """Start consuming entries and batching them indefinitely.

        Runs forever, batching entries by measurement and flushing when:
        - Batch age exceeds timeout_ms, or
        - Input queue is empty for 1 second

        Entry that triggers timeout is included in the flushed batch.
        """
        logger.info("Starting batch consumer")
        batch, batch_ms = self._reset_batch()

        while True:
            try:
                entry: Entry = self.queue.get(timeout=1.0)

                # Initialize batch timestamp on first entry
                if batch_ms == 0:
                    batch_ms = entry.ms

                # Add entry to current batch
                measurement = entry.json["measurement"]
                batch.setdefault(measurement, []).append(entry.json)

                # Flush if batch is old enough to flush
                if entry.ms - batch_ms >= self.timeout_ms:
                    logger.debug(
                        "Batch timeout reached (%d ms), flushing %d measurements",
                        entry.ms - batch_ms,
                        len(batch),
                    )
                    self.writer.send_batch(batch)
                    batch, batch_ms = self._reset_batch()

            except queue.Empty:
                if batch:
                    logger.debug(
                        "Queue idle for 1s, flushing batch with %d measurements",
                        len(batch),
                    )
                    self.writer.send_batch(batch)
                    batch, batch_ms = self._reset_batch()
