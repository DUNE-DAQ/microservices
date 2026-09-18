"""TimescaleDB writer and batch consumer for OpMon entries.

This module handles the persistence of monitoring entries from Kafka into
TimescaleDB, with automatic schema creation, batching, and error handling.
"""

import logging
import multiprocessing
import os
import queue
import signal
import threading
import time
from dataclasses import dataclass
from datetime import timezone
from typing import Protocol
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


class BatchSink(Protocol):
    """Anything a BatchConsumer can flush a batch into."""

    def send_batch(self, batch: BatchData) -> None:
        """Persist a batch of entries."""
        ...


class SizedQueue(Protocol):
    """Any queue whose depth can be sampled, in-process or cross-process."""

    def qsize(self) -> int:
        """Return the approximate number of items in the queue."""
        ...


@dataclass
class Entry:
    """A transformed OpMon entry ready for batch insertion.

    Attributes:
        json: Dictionary containing 'measurement', 'fields', 'tags', and 'time'.
    """

    json: dict
    ms: int


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
            Column("session", Text, nullable=False),
            Column("application", Text, nullable=False),
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
        self.uri = uri
        self.table_name = table_name
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


def _writer_process_main(
    uri: str,
    table_name: str,
    batch_queue: multiprocessing.Queue,
    log_level: int,
) -> None:
    """Entry point of the writer process: drain batches until the sentinel.

    Runs in a freshly spawned interpreter, so it builds its own engine and
    reconfigures logging rather than inheriting either from the parent.

    Args:
        uri: PostgreSQL connection URI.
        table_name: Name of the table to write into.
        batch_queue: Handoff queue; a None item means shut down.
        log_level: Logging level to mirror the parent's verbosity.
    """
    # The parent owns shutdown, via the sentinel. Ignoring SIGINT here keeps
    # a Ctrl-C delivered to the whole process group from killing this process
    # with batches still queued.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s [writer] %(message)s",
        level=log_level,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Writer process started (pid %d)", os.getpid())

    try:
        # The parent has already created the database and table.
        writer = TimescaleWriter(uri, table_name, create_if_missing=False)
    except Exception:
        logger.exception("Writer process failed to connect, exiting")
        return

    while (batch := batch_queue.get()) is not None:
        try:
            writer.send_batch(batch)
        except Exception:
            # send_batch handles database errors itself; anything reaching
            # here is unexpected, and must not take the process down with it.
            logger.exception("Unexpected error writing batch, batch dropped")

    logger.info("Writer process stopped")


class WriterProcess:
    """Runs a TimescaleWriter's inserts in a separate process.

    Decouples batching from the database round trip: the batch consumer
    hands a batch over and goes straight back to draining its input queue
    instead of blocking for the length of the insert. Unlike a thread, a
    separate process also keeps serialization and driver work off this
    interpreter's GIL, so a slow insert cannot stall the Kafka callback.

    The handoff queue is deliberately bounded. When TimescaleDB cannot keep
    up, `send_batch` blocks, which pushes back on the consumer rather than
    growing an unbounded backlog of pending batches in memory.

    The process is spawned rather than forked so it inherits no sockets or
    pooled connections from the parent's engine, which cannot safely be
    shared across a fork.
    """

    def __init__(
        self,
        writer: TimescaleWriter,
        *,
        max_pending: int = 4,
        log_level: int = logging.INFO,
    ) -> None:
        """Initialize the writer process.

        Args:
            writer: Writer whose connection settings the process reuses, and
                whose connection the parent keeps for health checks.
            max_pending: Batches that may await writing before send_batch blocks.
            log_level: Logging level to apply inside the writer process.
        """
        self._writer = writer
        ctx = multiprocessing.get_context("spawn")
        self._queue: multiprocessing.Queue = ctx.Queue(maxsize=max_pending)
        self._process = ctx.Process(
            target=_writer_process_main,
            args=(writer.uri, writer.table_name, self._queue, log_level),
            name="timescale-writer",
            daemon=True,
        )

    @property
    def pending_queue(self) -> SizedQueue:
        """Queue of batches waiting to be written, for monitoring."""
        return self._queue

    def start(self) -> None:
        """Start the writer process."""
        self._process.start()
        logger.info("Writer process spawned (pid %s)", self._process.pid)

    def send_batch(self, batch: BatchData) -> None:
        """Hand a batch to the writer process, blocking if it is behind.

        Args:
            batch: Dictionary mapping measurement names to lists of entry dicts.
        """
        if not batch:
            return

        # A plain blocking put would hang forever if the writer process died
        # with its queue full, so liveness is rechecked while waiting.
        while True:
            try:
                self._queue.put(batch, timeout=1.0)
            except queue.Full:
                if not self._process.is_alive():
                    logger.error("Writer process is dead, dropping batch")
                    return
            else:
                return

    def is_healthy(self) -> bool:
        """Check that the writer process is alive and the database reachable.

        A dead writer process silently drops every batch, so it has to count
        as unhealthy even while the connection itself is fine.

        Returns:
            True if the process is running and the database responds.
        """
        return self._process.is_alive() and self._writer.is_healthy()

    def stop(self, timeout: float = 10.0) -> None:
        """Flush pending batches and stop the writer process.

        Args:
            timeout: Seconds to wait for the pending batches to be written.
        """
        if not self._process.is_alive():
            return

        deadline = time.monotonic() + timeout
        try:
            self._queue.put(None, timeout=timeout)
        except queue.Full:
            logger.warning("Writer process did not drain, dropping pending batches")
        else:
            self._process.join(timeout=max(0.0, deadline - time.monotonic()))

        if self._process.is_alive():
            logger.warning("Writer process still busy at shutdown, terminating it")
            self._process.terminate()
            self._process.join(timeout=1.0)


class QueueMonitor:
    """Logs the depth of the pipeline's queues on a background thread.

    Queue depth is the signal that says which stage is the bottleneck: a
    growing entry queue means batching cannot keep up with Kafka, while a
    full pending-batch queue means TimescaleDB cannot keep up with batching.
    """

    def __init__(self, queues: dict[str, SizedQueue], interval_s: float = 10.0) -> None:
        """Initialize the queue monitor.

        Args:
            queues: Mapping of display name to queue to sample.
            interval_s: Seconds between samples.
        """
        self._queues = queues
        self._interval_s = interval_s
        self._peaks: dict[str, int] = dict.fromkeys(queues, 0)
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="queue-monitor", daemon=True
        )

    def start(self) -> None:
        """Start sampling queue depths."""
        self._thread.start()
        logger.info(
            "Queue monitor started, sampling %s every %.1fs",
            ", ".join(self._queues),
            self._interval_s,
        )

    def stop(self) -> None:
        """Stop sampling and log a final sample."""
        self._stop.set()
        self._log_depths()

    def _run(self) -> None:
        """Sample queue depths until stopped."""
        while not self._stop.wait(self._interval_s):
            self._log_depths()

    @staticmethod
    def _capacity(q: SizedQueue) -> int:
        """Return a queue's maximum size, or 0 when it is unbounded."""
        return getattr(q, "maxsize", 0) or 0

    def _log_depths(self) -> None:
        """Log one sample of every queue, and warn about any that are full.

        Never raises: a failed sample must not take the monitor thread down,
        or monitoring would stop silently for the rest of the process's life.
        """
        try:
            parts = []
            full = []
            for name, q in self._queues.items():
                depth = q.qsize()
                self._peaks[name] = max(self._peaks[name], depth)
                capacity = self._capacity(q)
                size = f"{depth}/{capacity}" if capacity else str(depth)
                parts.append(f"{name}={size} (peak {self._peaks[name]})")
                if capacity and depth >= capacity:
                    full.append(name)
        except Exception:
            logger.exception("Failed to sample queue depths")
            return

        logger.info("Queue depths: %s", " ".join(parts))
        if full:
            logger.warning(
                "Queue(s) at capacity, upstream stages are being throttled: %s",
                ", ".join(full),
            )


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
        tags = {"sub"*i + "element": self._strip_nul(s) for i, s in enumerate(opmon_id.substructure)}
        tags.update({k: self._strip_nul(v) for k, v in entry.custom_origin.items()})
        payload = {
            "session": self._strip_nul(opmon_id.session),
            "application": self._strip_nul(opmon_id.application),
            "measurement": self._strip_nul(entry.measurement),
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
        self, input_queue: queue.Queue[Entry], writer: BatchSink, timeout_ms: int
    ) -> None:
        """Initialize batch consumer.

        Args:
            input_queue: Queue of Entry objects to consume.
            writer: Sink for batch writes, e.g. a WriterProcess.
            timeout_ms: Maximum millisecond age of a batch before forced flush.
        """
        self.queue = input_queue
        self.writer = writer
        self.timeout_ms = timeout_ms

    def _reset_batch(self) -> tuple[BatchData, int]:
        """Reset batch and batch_start to empty state.

        Returns:
            Tuple of (empty_batch, reset_start_time).
        """
        return {}, 0

    def start(self) -> None:
        """Start consuming entries and batching them indefinitely.

        Runs forever, batching entries by measurement and flushing when:
        - The batch spans more than timeout_ms of entry time, or
        - Input queue is empty for 1 second

        Batch age is measured against the entries' own embedded timestamps,
        so a batch covers a bounded window of monitoring time regardless of
        how fast the entries in it happen to arrive. Both ends of the
        comparison come from entry time, so they stay on one clock; the
        idle flush is what bounds a batch whose timestamps stop advancing.
        """
        logger.info("Starting batch consumer")
        batch, batch_start = self._reset_batch()

        while True:
            try:
                entry: Entry = self.queue.get(timeout=1.0)

                # Initialize batch start time on first entry
                if not batch:
                    batch_start = entry.ms

                # Add entry to current batch
                measurement = entry.json["measurement"]
                batch.setdefault(measurement, []).append(entry.json)

                # Flush if batch is old enough to flush
                elapsed_ms = entry.ms - batch_start
                if elapsed_ms >= self.timeout_ms:
                    logger.debug(
                        "Batch timeout reached (%d ms), flushing %d measurements",
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