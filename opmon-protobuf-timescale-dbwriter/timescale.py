"""TimescaleDB writer and batch consumer for OpMon entries.

This module handles the persistence of monitoring entries from Kafka into
TimescaleDB, with automatic schema creation, batching, and error handling.
"""

import logging
import queue
import time
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

# Type alias for batch data structure: {measurement_name: [entry_dicts]}
BatchData = dict[str, list[dict]]


@dataclass
class Entry:
    """A transformed OpMon entry ready for batch insertion.

    Attributes:
        json: Dictionary containing 'measurement', 'fields', 'tags', and 'time'.
    """

    json: dict


class SchemaManager:
    """Manages the single TimescaleDB table all measurements are written to.

    Creates the table on-demand with hypertable configuration.
    """

    def __init__(self, engine: Engine, table_name: str) -> None:
        """Initialize schema manager.

        Args:
            engine: SQLAlchemy Engine connected to TimescaleDB.
            table_name: Name of the table to write all measurements into.
        """
        self.engine = engine
        self.table_name = table_name
        self.metadata = MetaData()
        self.table = Table(
            table_name,
            self.metadata,
            Column("time", DateTime(timezone=True), nullable=False),
            Column("measurement", Text, nullable=False),
            Column("tags", JSONB, nullable=False),
            Column("fields", JSONB, nullable=False),
            Index(f"ix_{table_name}_measurement", "measurement"),
            Index(f"ix_{table_name}_tags_gin", "tags", postgresql_using="gin"),
            Index(f"ix_{table_name}_fields_gin", "fields", postgresql_using="gin"),
        )

    def ensure_table(self) -> Table:
        """Create the table (and hypertable) if it doesn't already exist.

        Returns:
            SQLAlchemy Table object.
        """
        with self.engine.begin() as conn:
            if not self.engine.dialect.has_table(conn, self.table_name):
                self.table.create(conn)
                # create_hypertable() resolves its argument as an identifier,
                # folding unquoted text to lowercase. CREATE TABLE preserves
                # case, so a mixed-case name must be passed pre-quoted to
                # refer to the table that was just created.
                quoted = conn.dialect.identifier_preparer.quote(self.table_name)
                conn.execute(
                    text(
                        f"SELECT create_hypertable('{quoted}', 'time', "
                        "if_not_exists => TRUE);"
                    )
                )
        return self.table


class TimescaleWriter:
    """Manages database connections and batch writes to TimescaleDB."""

    def __init__(self, uri: str, table_name: str, *, create_if_missing: bool = True) -> None:
        """Initialize TimescaleDB writer.

        Args:
            uri: PostgreSQL connection URI.
            table_name: Name of the table to use in TimescaleDB.
            create_if_missing: If True, create database if it doesn't exist.

        Raises:
            ConnectionError: If database doesn't exist and create_if_missing is False,
                or if URI has no database name.
        """
        self.engine = self._connect(uri, create_if_missing=create_if_missing)
        self.schema_manager = SchemaManager(self.engine, table_name)
        self.table = self.schema_manager.ensure_table()

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

        records = [record for group in batch.values() for record in group]
        logger.info(
            "Sending %d points across %d measurements", len(records), len(batch)
        )

        try:
            with self.engine.begin() as conn:
                conn.execute(self.table.insert(), records)
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

    @staticmethod
    def _strip_nul(value):
        """Remove NUL characters, which Postgres text/JSONB columns reject.

        Protobuf string fields may legally contain '\\x00' (e.g. from a
        producer writing an uninitialized buffer), but Postgres raises
        UntranslatableCharacter on it, which would otherwise fail the
        whole batch insert this entry ends up in.
        """
        return value.replace("\x00", "") if isinstance(value, str) else value

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
                fields[key] = self._strip_nul(getattr(value, kind))

        opmon_id = entry.origin
        tags = {
            "session": self._strip_nul(opmon_id.session),
            "application": self._strip_nul(opmon_id.application),
        }
        for i, s in enumerate(opmon_id.substructure):
            name = "sub" * i + "element"
            tags[name] = self._strip_nul(s)
        tags.update({k: self._strip_nul(v) for k, v in entry.custom_origin.items()})

        payload = {
            "measurement": self._strip_nul(entry.measurement),
            "fields": fields,
            "tags": tags,
            "time": entry.time.ToDatetime(tzinfo=timezone.utc),
        }
        return Entry(json=payload)

    def process_entry(self, entry: opmon_schema.OpMonEntry) -> None:
        """Process and queue a single OpMon entry.

        Args:
            entry: OpMon protobuf entry from Kafka.

        Logs errors if transformation fails but does not propagate exceptions.
        """
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

    def _reset_batch(self) -> tuple[BatchData, float]:
        """Reset batch and batch_start to empty state.

        Returns:
            Tuple of (empty_batch, reset_start_time).
        """
        return {}, 0.0

    def start(self) -> None:
        """Start consuming entries and batching them indefinitely.

        Runs forever, batching entries by measurement and flushing when:
        - Wall-clock time since the batch started exceeds timeout_ms, or
        - Input queue is empty for 1 second

        Batch age is measured against wall-clock arrival time rather than
        the entries' own embedded timestamps, so batching stays bounded
        even when consuming a backlog of old messages in quick succession.
        """
        logger.info("Starting batch consumer")
        batch, batch_start = self._reset_batch()

        while True:
            try:
                entry: Entry = self.queue.get(timeout=1.0)

                # Initialize batch start time on first entry
                if not batch:
                    batch_start = time.monotonic()

                # Add entry to current batch
                measurement = entry.json["measurement"]
                batch.setdefault(measurement, []).append(entry.json)

                # Flush if batch is old enough to flush
                elapsed_ms = (time.monotonic() - batch_start) * 1000
                if elapsed_ms >= self.timeout_ms:
                    logger.debug(
                        "Batch timeout reached (%.0f ms), flushing %d measurements",
                        elapsed_ms,
                        len(batch),
                    )
                    self.writer.send_batch(batch)
                    batch, batch_start = self._reset_batch()

            except queue.Empty:
                if batch:
                    logger.debug(
                        "Queue idle for 1s, flushing batch with %d measurements",
                        len(batch),
                    )
                    self.writer.send_batch(batch)
                    batch, batch_start = self._reset_batch()
