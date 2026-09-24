"""TimescaleDB writer and batch consumer for OpMon entries.

This module handles the persistence of monitoring entries from Kafka into
TimescaleDB, with automatic schema creation, batching, and error handling.

The writer also monitors itself: MetricsPublisher samples the pipeline on a
thread of its own and pushes the result onto the front of the entry queue
as an ordinary entry, so it is batched and written through the same path
as any other entry -- ahead of whatever backlog is already waiting -- and
the service's own state is queryable beside the applications it records.

- Measurement: dunedaq.microservices.opmon.TimescaleDBInfo
- session: the Kafka consumer group
- application: timescaledb_writer
- tags: {}
- fields = {"entry_queue_size": <size of entry queue>,
            "writer_queue_size": <size of writer queue>,
            "entries_created": <entries queued this interval>,
            "entries_dequeued": <entries taken off the entry queue this interval>,
            "batches_processed": <batches flushed this interval>,
            "entries_rejected": <entries dropped on a full queue this interval>,
            "entry_queue_rate_gbps": <rate entries arrived into the entry queue, in GB/s>,
            "writer_queue_rate_gbps": <rate entries left the entry queue for batching, in GB/s>
        }

The queue sizes are instantaneous depths, while the four counters are
counts over the interval just ended, reset at every sample, so each row
reads as a rate over the sampling period rather than as a running total
to be differenced. entries_dequeued divided by the sampling period is the
entry queue's drain rate, i.e. how fast data is actually leaving the queue,
as distinct from entries_created's arrival rate.
"""

import logging
import multiprocessing
import os
import queue
import signal
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlparse

import opmonlib.opmon_entry_pb2 as opmon_schema
import psycopg
from monitoring_dataclasses import QueueMetrics
from psycopg.types.json import Jsonb
from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Index,
    MetaData,
    Table,
    Text,
    create_engine,
    make_url,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import OperationalError
from sqlalchemy_utils import create_database, database_exists

logger = logging.getLogger(__name__)

# Type alias for batch data structure: {measurement_name: [entry_dicts]}
BatchData = dict[str, list[dict]]

# Identity this service reports its own metrics under, so they sit in the
# same table as the entries it writes and can be plotted beside them.
METRICS_MEASUREMENT = "dunedaq.microservices.opmon.TimescaleDBInfo"
METRICS_APPLICATION = "timescaledb_writer"
DEFAULT_METRICS_RATE_HZ = 0.1


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


@dataclass(frozen=True)
class BoundedQueueView:
    """Reports a multiprocessing queue's depth and bound like a queue.Queue.

    multiprocessing.Queue keeps its bound in _maxsize and substitutes
    SEM_VALUE_MAX when unbounded, so the real bound is passed in.
    """

    queue: multiprocessing.Queue

    def qsize(self) -> int:
        """Return the approximate number of items in the queue."""
        return self.queue.qsize()


@dataclass
class Entry:
    """A transformed OpMon entry ready for batch insertion.

    Attributes:
        json: Dictionary containing 'measurement', 'fields', 'tags', and 'time'.
        size_bytes: Size of the original protobuf entry, for data-rate metrics.
    """

    json: dict
    ms: int
    size_bytes: int = 0


class EntryQueue(queue.Queue):
    """FIFO queue of entries that also allows jumping one to the front.

    put_front lets the writer's own metrics sample ride the same queue,
    batching and write path as the entries it describes -- see
    MetricsPublisher -- while skipping ahead of whatever backlog is
    already waiting. That backlog is exactly when the queue-depth metric
    most needs to get through promptly instead of aging behind it.
    """

    def put_front(self, item: Entry) -> None:
        """Insert an item at the front of the queue, ahead of anything waiting."""
        with self.mutex:
            self.queue.appendleft(item)
            self.unfinished_tasks += 1
            self.not_empty.notify()

def _table_name_for_measurement(measurement: str) -> str:
    """Derive a SQL-safe table name from a dotted measurement name.

    Measurement names are of the form "foo.bar.foobar.barfoo"; dots aren't
    valid in an unquoted Postgres identifier, so they become underscores.
    """
    return measurement.replace(".", "_")


class SchemaManager:
    """Creates and caches one TimescaleDB hypertable per measurement.

    Each measurement gets its own table, named after it, created on-demand
    the first time that measurement is seen.
    """

    def __init__(self, engine: Engine) -> None:
        """Initialize schema manager.

        Args:
            engine: SQLAlchemy Engine connected to TimescaleDB.
        """
        self.engine = engine
        self.metadata = MetaData()
        self._tables: dict[str, Table] = {}

    def ensure_table(self, measurement: str) -> Table:
        """Return the table for a measurement, creating it if needed.

        Args:
            measurement: Dotted measurement name to derive the table from.

        Returns:
            SQLAlchemy Table object for that measurement.
        """
        table_name = _table_name_for_measurement(measurement)
        table = self._tables.get(table_name)
        if table is not None:
            return table

        table = Table(
            table_name,
            self.metadata,
            Column("time", DateTime(timezone=True), nullable=False),
            Column("session", Text, nullable=False),
            Column("application", Text, nullable=False),
            Column("tags", JSONB, nullable=False),
            Column("fields", JSONB, nullable=False),
            Index(f"ix_{table_name}_session", "session"),
            Index(f"ix_{table_name}_application", "application"),
            Index(f"ix_{table_name}_tags_gin", "tags", postgresql_using="gin"),
        )

        try:
            with self.engine.begin() as conn:
                if not self.engine.dialect.has_table(conn, table_name):
                    table.create(conn)
                    quoted = conn.dialect.identifier_preparer.quote(table_name)
                    conn.execute(
                        text(
                            f"SELECT create_hypertable('{quoted}', 'time', "
                            "if_not_exists => TRUE);"
                        )
                    )
        except Exception:
            # Table() already registered itself in self.metadata on
            # construction above; undo that on failure, or every retry
            # for this measurement fails with "already defined" instead
            # of actually retrying the creation.
            self.metadata.remove(table)
            raise

        self._tables[table_name] = table
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
        self.uri = uri
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

        # send_batch() uses the psycopg3 cursor.copy() API directly on the
        # underlying driver connection. A bare "postgres(ql)://" URI lets
        # SQLAlchemy pick whatever PostgreSQL driver it defaults to (psycopg2,
        # if installed), so pin the driver explicitly rather than relying on
        # environment happenstance.
        url = make_url(uri).set(drivername="postgresql+psycopg")
        engine = create_engine(url)
        if database_exists(engine.url):
            return engine

        if not create_if_missing:
            raise ConnectionError(f"Cannot find DB {uri}")

        create_database(engine.url)
        return engine

    def send_batch(self, batch: BatchData) -> None:
        """Send a batch of entries to TimescaleDB, one COPY per measurement.

        Uses COPY rather than a parameterized multi-row INSERT: COPY skips
        per-row query planning and parameter binding, which matters at the
        rates this is meant to sustain. It bypasses SQLAlchemy Core's
        execute path, so it goes straight through the underlying psycopg
        connection pulled from the engine's own pool.

        Args:
            batch: Dictionary mapping measurement names to lists of entry dicts.
        """
        if not batch:
            return

        total = sum(len(group) for group in batch.values())
        logger.info(
            "Sending %d points across %d measurements", total, len(batch)
        )

        try:
            tables = {
                measurement: self.schema_manager.ensure_table(measurement)
                for measurement in batch
            }
        except OperationalError:
            logger.exception("TimescaleDB connection error occurred")
            return

        try:
            raw_conn = self.engine.raw_connection()
        except OperationalError:
            logger.exception("TimescaleDB connection error occurred")
            return

        conn = raw_conn.driver_connection
        try:
            with conn.cursor() as cur:
                for measurement, records in batch.items():
                    columns = tables[measurement].columns
                    column_names = ", ".join(col.name for col in columns)
                    quoted_table = self.engine.dialect.identifier_preparer.quote(
                        tables[measurement].name
                    )
                    copy_sql = f"COPY {quoted_table} ({column_names}) FROM STDIN"
                    with cur.copy(copy_sql) as copy:
                        for record in records:
                            copy.write_row(
                                tuple(
                                    Jsonb(record[col.name])
                                    if isinstance(col.type, JSONB)
                                    else record[col.name]
                                    for col in columns
                                )
                            )
            conn.commit()
        except psycopg.OperationalError:
            conn.rollback()
            logger.exception("TimescaleDB connection error occurred")
        except psycopg.Error:
            conn.rollback()
            logger.exception("Failed to write batch to TimescaleDB")
        finally:
            raw_conn.close()


def _writer_process_main(
    uri: str,
    batch_queue: multiprocessing.Queue,
    log_level: int,
) -> None:
    """Entry point of the writer process: drain batches until the sentinel.

    Runs in a freshly spawned interpreter, so it builds its own engine and
    reconfigures logging rather than inheriting either from the parent.

    Args:
        uri: PostgreSQL connection URI.
        batch_queue: Handoff queue; a None item means shut down.
        log_level: Logging level to mirror the parent's verbosity.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s [writer] %(message)s",
        level=log_level,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Writer process started (pid %d)", os.getpid())

    try:
        # The parent has already created the database; each measurement's
        # table is created lazily here, the first time it is written.
        writer = TimescaleWriter(uri, create_if_missing=False)
    except Exception:
        logger.exception("Writer process failed to connect, exiting")
        raise SystemExit(1) from None

    while (batch := batch_queue.get()) is not None:
        try:
            writer.send_batch(batch)
        except Exception:
            # send_batch handles database errors; nothing else gets to kill
            # the process and strand the queue.
            logger.exception("Unexpected error writing batch, batch dropped")

    logger.info("Writer process stopped, shutdown sentinel received")


class WriterProcess:
    """Runs a TimescaleWriter's inserts in a separate process.

    The handoff queue is bounded, so send_batch blocks rather than piling up
    batches when the database falls behind.

    Spawned rather than forked: a forked child would inherit the parent's
    pooled connections and sockets, which cannot be shared across a fork.

    A writer that dies -- e.g. a connection attempt that raced the database
    coming up -- is respawned automatically rather than left dead for the
    rest of the pod's life, backed off so a persistent failure doesn't spin.
    """

    def __init__(
        self,
        writer: TimescaleWriter,
        *,
        log_level: int = logging.INFO,
        respawn_backoff_s: float = 5.0,
    ) -> None:
        """Initialize the writer process.

        Args:
            writer: Writer whose connection settings the process reuses, and
                whose connection the parent keeps for health checks.
            log_level: Logging level to apply inside the writer process.
            respawn_backoff_s: Minimum seconds between respawn attempts, so a
                writer that keeps failing to connect doesn't spin.
        """
        self._writer = writer
        self._log_level = log_level
        self._respawn_backoff_s = respawn_backoff_s
        self._last_respawn = float("-inf")
        self._ctx = multiprocessing.get_context("spawn")
        self._queue: multiprocessing.Queue = self._ctx.Queue()
        self._process = self._make_process()

    def _make_process(self) -> multiprocessing.process.BaseProcess:
        """Build a fresh writer process bound to the same handoff queue."""
        return self._ctx.Process(
            target=_writer_process_main,
            args=(self._writer.uri, self._queue, self._log_level),
            name="timescale-writer",
            daemon=True,
        )

    @property
    def pending_queue(self) -> SizedQueue:
        """Queue of batches waiting to be written, for monitoring."""
        return BoundedQueueView(self._queue)

    def start(self) -> None:
        """Start the writer process."""
        self._process.start()
        logger.info("Writer process spawned (pid %s)", self._process.pid)

    def send_batch(self, batch: BatchData) -> None:
        """Queue a batch for the writer process, blocking if it is behind."""
        if not batch:
            return

        # Checked up front: a put into a queue nobody reads still succeeds
        # while there is room, so a dead writer silently swallows the first
        # max_pending batches before anything looks wrong.
        if not self._ensure_alive():
            return

        # A plain blocking put would hang forever if the writer died with its
        # queue full, so liveness is rechecked while waiting.
        while True:
            try:
                self._queue.put(batch, timeout=1.0)
            except queue.Full:
                if not self._ensure_alive():
                    return
            else:
                return

    def _ensure_alive(self) -> bool:
        """Respawn the writer process if it died, backed off from spinning.

        Returns:
            True if a live writer process is running afterward and it's
            safe to queue batches to it; False if it is dead and still
            within the backoff window since the last respawn attempt.
        """
        if self._process.is_alive():
            return True

        self._log_death()
        now = time.monotonic()
        if now - self._last_respawn < self._respawn_backoff_s:
            logger.error("Writer process still recovering, dropping batch")
            return False

        self._last_respawn = now
        self._process = self._make_process()
        self._process.start()
        logger.warning("Writer process respawned (pid %s)", self._process.pid)
        return True

    def _log_death(self) -> None:
        """Report the dead writer process, with the exit code that says why.

        The exit code is the only evidence left of how it went: 0 for a
        clean return, 1 for an unhandled exception, and -N for the signal
        that killed it (-9 out of memory, -11 segfault). A signal leaves
        nothing in either process's log, so it has to be printed here.
        """
        logger.error(
            "Writer process is dead (exitcode %s)", self._process.exitcode
        )

    def is_healthy(self) -> bool:
        """Check the writer process is alive and the database reachable.

        A dead writer drops every batch while SELECT 1 still succeeds.
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


class PipelineCounters:
    """Tallies of what the pipeline has done since the last metrics sample.

    Incremented from the subscriber's callback threads and the batch
    consumer thread while being read by the publisher thread, so every
    access is taken under the lock: a bare ``+=`` is a read-modify-write
    that can lose increments across threads.
    """

    def __init__(self) -> None:
        """Initialize all counters at zero."""
        self._lock = threading.Lock()
        self._entries_created = 0
        self._entries_dequeued = 0
        self._batches_processed = 0
        self._entries_rejected = 0
        self._bytes_created = 0
        self._bytes_dequeued = 0

    def entry_created(self, size_bytes: int = 0) -> None:
        """Record one entry queued for batching.

        Args:
            size_bytes: Size of the entry's original protobuf, for the
                entry queue's arrival data rate.
        """
        with self._lock:
            self._entries_created += 1
            self._bytes_created += size_bytes

    def entry_dequeued(self, size_bytes: int = 0) -> None:
        """Record one entry taken off the entry queue for batching.

        Args:
            size_bytes: Size of the entry's original protobuf, for the
                entry queue's drain data rate.
        """
        with self._lock:
            self._entries_dequeued += 1
            self._bytes_dequeued += size_bytes

    def entry_rejected(self) -> None:
        """Record one entry dropped because the entry queue was full."""
        with self._lock:
            self._entries_rejected += 1

    def batch_processed(self) -> None:
        """Record one batch handed to the writer."""
        with self._lock:
            self._batches_processed += 1

    def sample(self) -> tuple[int, int, int, int, int, int]:
        """Read the counters and reset them for the next interval.

        Returns:
            Tuple of (entries_created, entries_dequeued, batches_processed,
            entries_rejected, bytes_created, bytes_dequeued), each counting
            only the interval since the previous sample, so they read as
            rates over the sampling period.
        """
        with self._lock:
            counts = (
                self._entries_created,
                self._entries_dequeued,
                self._batches_processed,
                self._entries_rejected,
                self._bytes_created,
                self._bytes_dequeued,
            )
            self._entries_created = 0
            self._entries_dequeued = 0
            self._batches_processed = 0
            self._entries_rejected = 0
            self._bytes_created = 0
            self._bytes_dequeued = 0
            return counts


class MetricsPublisher:
    """Publishes the writer's own queue metrics into the entry pipeline.

    Each sample is pushed onto the front of the entry queue as an ordinary
    Entry, so it rides the same batching and write path as the entries it
    measures, lands in the same table as the applications it records, and
    is not stuck waiting behind whatever backlog it is reporting on.

    Sampling its own input queue means the sample is reported one flush
    later than it was taken, which is well inside the sampling period at
    the rates this runs at.
    """

    def __init__(
        self,
        counters: PipelineCounters,
        entry_queue: EntryQueue,
        batch_queue: SizedQueue,
        *,
        session: str,
        rate_hz: float = DEFAULT_METRICS_RATE_HZ,
    ) -> None:
        """Initialize the metrics publisher.

        Args:
            counters: Counters the pipeline increments as it runs.
            entry_queue: Queue of entries waiting to be batched -- sampled
                for its depth and given the published sample, at the front.
            batch_queue: Queue of batches waiting on the writer process.
            session: Session to report under, i.e. the Kafka consumer group.
            rate_hz: Samples per second.

        Raises:
            ValueError: If rate_hz is not positive.
        """
        if rate_hz <= 0:
            raise ValueError(f"Metrics rate must be positive, got {rate_hz}")

        self._counters = counters
        self._entry_queue = entry_queue
        self._batch_queue = batch_queue
        self._session = session
        self._rate_hz = rate_hz
        self._interval_s = 1.0 / rate_hz
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="metrics-publisher", daemon=True
        )

    def start(self) -> None:
        """Start publishing metrics."""
        self._thread.start()
        logger.info(
            "Metrics publisher started, reporting %s every %.1fs (%.3g Hz)",
            METRICS_MEASUREMENT,
            self._interval_s,
            self._rate_hz,
        )

    def stop(self) -> None:
        """Stop publishing metrics."""
        self._stop.set()

    def _run(self) -> None:
        """Publish one sample per interval until stopped."""
        while not self._stop.wait(self._interval_s):
            self._publish()

    def sample(self) -> QueueMetrics:
        """Take one sample of the queue depths and counters."""
        created, dequeued, processed, rejected, bytes_created, bytes_dequeued = (
            self._counters.sample()
        )
        return QueueMetrics(
            entry_queue_size=self._entry_queue.qsize(),
            writer_queue_size=self._batch_queue.qsize(),
            entries_created=created,
            entries_dequeued=dequeued,
            batches_processed=processed,
            entries_rejected=rejected,
            entry_queue_rate_gbps=bytes_created / self._interval_s / 1e9,
            writer_queue_rate_gbps=bytes_dequeued / self._interval_s / 1e9,
        )

    def _to_entry(self, metrics: QueueMetrics) -> Entry:
        """Wrap a sample as an Entry the batch consumer can write.

        Args:
            metrics: Sample to publish.

        Returns:
            Entry carrying the metrics as its fields.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "session": self._session,
            "application": METRICS_APPLICATION,
            "measurement": METRICS_MEASUREMENT,
            "fields": asdict(metrics),
            "tags": {},
            "time": now,
        }
        return Entry(json=payload, ms=int(now.timestamp() * 1000))

    def _publish(self) -> None:
        """Sample once and queue the result.

        Never raises: a failed sample must not take the publisher thread
        down, or the writer would stop reporting itself for the rest of
        the process's life.
        """
        try:
            metrics = self.sample()
            logger.info("Publishing queue metrics | Batches: %d, Created: %d, Dequeued: %d, Rejected: %d, Entry Queue: %d, Writer Queue: %d, Entry Rate: %.4f GB/s, Writer Rate: %.4f GB/s", metrics.batches_processed, metrics.entries_created, metrics.entries_dequeued, metrics.entries_rejected, metrics.entry_queue_size, metrics.writer_queue_size, metrics.entry_queue_rate_gbps, metrics.writer_queue_rate_gbps)
            self._entry_queue.put_front(self._to_entry(metrics))
        except Exception:
            logger.exception("Failed to publish queue metrics")
        else:
            logger.debug("Published queue metrics: %s", metrics)


class OpMonTransformer:
    """Transforms raw OpMon protobuf entries into queue-ready Entry objects."""

    def __init__(
        self, q: queue.Queue[Entry], counters: PipelineCounters | None = None
    ) -> None:
        """Initialize transformer with output queue.

        Args:
            q: Queue to place transformed entries into.
            counters: Counters to record entries into; a private set is
                used when none is given, so the transformer works the same
                whether or not anything is publishing metrics.
        """
        self._q = q
        self._counters = counters or PipelineCounters()

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
        return Entry(
            json=payload,
            ms=entry.time.ToMilliseconds(),
            size_bytes=entry.ByteSize(),
        )

    def process_entry(self, entry: opmon_schema.OpMonEntry) -> None:
        """Process and queue a single OpMon entry.

        Args:
            entry: OpMon protobuf entry from Kafka.

        Logs errors if transformation fails but does not propagate exceptions.
        """
        try:
            transformed = self._to_entry(entry)
            self._q.put(transformed)
            self._counters.entry_created(transformed.size_bytes)
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
            self._counters.entry_rejected()
            logger.exception(
                "Entry queue full, dropping entry from %r",
                entry.origin.application,
            )


class BatchConsumer:
    """Batches entries and writes them to TimescaleDB with timeout-based flushing."""

    def __init__(
        self,
        input_queue: queue.Queue[Entry],
        writer: BatchSink,
        timeout_ms: int,
        counters: PipelineCounters | None = None,
    ) -> None:
        """Initialize batch consumer.

        Args:
            input_queue: Queue of Entry objects to consume.
            writer: Sink for batch writes, e.g. a WriterProcess.
            timeout_ms: Maximum millisecond age of a batch before forced flush.
            counters: Counters to record flushes into; a private set is
                used when none is given.
        """
        self.queue = input_queue
        self.writer = writer
        self.timeout_ms = timeout_ms
        self._counters = counters or PipelineCounters()

    def _reset_batch(self) -> tuple[BatchData, int]:
        """Reset batch and batch_start to empty state.

        Returns:
            Tuple of (empty_batch, reset_start_time).
        """
        return {}, 0

    def _flush(self, batch: BatchData) -> tuple[BatchData, int]:
        """Send a batch to the writer and start a fresh one.

        Args:
            batch: Batch to send.

        Returns:
            Tuple of (empty_batch, reset_start_time).
        """
        self.writer.send_batch(batch)
        self._counters.batch_processed()
        return self._reset_batch()

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
                self._counters.entry_dequeued(entry.size_bytes)

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
                    batch, batch_start = self._flush(batch)

            except queue.Empty:
                if batch:
                    logger.debug(
                        "Queue idle for 1s, flushing batch with %d measurements",
                        len(batch),
                    )
                    batch, batch_start = self._flush(batch)
