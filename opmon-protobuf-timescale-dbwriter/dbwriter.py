"""OpMon entries to TimescaleDB writer.

This service subscribes to OpMon entries on Kafka, transforms them,
batches them, and writes them to TimescaleDB with automatic schema
management and Kubernetes health probes.

This is part of the DUNE DAQ software, copyright 2020.
Licensing/copyright details are in the COPYING file that you should have
received with this code.
"""

import logging
import signal
import threading

import click
import kafkaopmon.OpMonSubscriber as opmon_sub

from health_server import HealthServer
from timescale import (
    BatchConsumer,
    EntryQueue,
    MetricsPublisher,
    OpMonTransformer,
    PipelineCounters,
    QueueMonitor,
    TimescaleWriter,
    WriterProcess,
)

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

# Default configuration values
DEFAULT_BOOTSTRAP_SERVER = "monkafka.cern.ch:30092"
DEFAULT_SUBSCRIBER_TIMEOUT_MS = 500
DEFAULT_DB_URI = "postgres://localhost:5432/test_timescaledb"
DEFAULT_BATCH_TIMEOUT_MS = 500
DEFAULT_MAX_PENDING_BATCHES = 4
DEFAULT_QUEUE_MONITOR_INTERVAL_S = 10.0
DEFAULT_METRICS_RATE_HZ = 0.1

# Session reported for the writer's own metrics when no consumer group was
# given; the subscriber then generates one that this process cannot see.
UNKNOWN_SESSION = "unknown"

logger = logging.getLogger(__name__)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--subscriber-bootstrap",
    type=click.STRING,
    default=DEFAULT_BOOTSTRAP_SERVER,
    help="bootstrap server and port of the OpMonSubscriber",
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
    default=DEFAULT_SUBSCRIBER_TIMEOUT_MS,
    help="timeout in ms used in the OpMonSubscriber",
)
@click.option(
    "--subscriber-topic",
    type=click.STRING,
    multiple=True,
    default=["opmon_stream"],
    help="Kafka topic(s) to subscribe to",
)
@click.option(
    "--timescaledb-uri",
    type=click.STRING,
    default=DEFAULT_DB_URI,
    help="URI of the timescaleDB server (e.g., postgres://user:pass@host:port/dbname)",
)
@click.option(
    "--timescaledb-create",
    is_flag=True,
    default=True,
    help="Creates the timescaledb if it does not exist",
)
@click.option(
    "--timescaledb-timeout",
    type=click.INT,
    default=DEFAULT_BATCH_TIMEOUT_MS,
    help="Size in ms of the batches sent to timescale",
)
@click.option(
    "--queue-monitor-interval",
    type=click.FLOAT,
    default=DEFAULT_QUEUE_MONITOR_INTERVAL_S,
    help="Seconds between queue depth log lines (0 disables monitoring)",
)
@click.option(
    "--metrics-rate",
    type=click.FLOAT,
    default=DEFAULT_METRICS_RATE_HZ,
    help="Rate in Hz at which the writer's own queue metrics are written to TimescaleDB (0 disables)",
)
@click.option(
    "--health-port",
    type=click.INT,
    default=None,
    help="Port for HTTP health endpoint (if not set, no health endpoint)",
)
@click.option("--debug", is_flag=True, default=False, help="Enable debug logging")
def cli(  # noqa: PLR0913
    *,
    subscriber_bootstrap: str,
    subscriber_group: str | None,
    subscriber_timeout: int,
    subscriber_topic: tuple[str, ...],
    timescaledb_uri: str,
    timescaledb_create: bool,
    timescaledb_timeout: int,
    queue_monitor_interval: float,
    metrics_rate: float,
    health_port: int | None,
    debug: bool,
) -> None:
    """Run OpMon to TimescaleDB writer service.

    Subscribes to Kafka topics, transforms OpMon protobuf entries,
    batches them, and writes to TimescaleDB.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=log_level,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Starting OpMon TimescaleDB writer, one table per measurement")
    logger.debug(
        "Config: bootstrap=%s, topics=%s, batch_timeout_ms=%d",
        subscriber_bootstrap,
        subscriber_topic,
        timescaledb_timeout,
    )

    writer = TimescaleWriter(timescaledb_uri, create_if_missing=timescaledb_create)
    logger.info("Connected to TimescaleDB")

    # Inserts run in their own process so batching isn't blocked on the
    # write, and driver work stays off this interpreter's GIL.
    async_writer = WriterProcess(
        writer, log_level=log_level
    )
    async_writer.start()

    if health_port is not None:
        HealthServer(health_port, async_writer.is_healthy).start()

    q = EntryQueue()
    sub = opmon_sub.OpMonSubscriber(
        bootstrap=subscriber_bootstrap,
        topics=subscriber_topic,
        group_id=subscriber_group,
        timeout_ms=subscriber_timeout,
    )

    counters = PipelineCounters()
    transformer = OpMonTransformer(q, counters)

    sub.add_callback(
        name="to_timescale_db",
        function=transformer.process_entry,
    )

    consumer = BatchConsumer(q, async_writer, timescaledb_timeout, counters)
    threading.Thread(target=consumer.start, daemon=True).start()

    logger.info("Batch consumer thread started")

    # The writer reports on itself through its own pipeline, so this has to
    # come up after the consumer that drains it.
    publisher = None
    if metrics_rate > 0:
        publisher = MetricsPublisher(
            counters,
            batch_queue=async_writer.pending_queue,
            entry_queue=q,
            session=subscriber_group or UNKNOWN_SESSION,
            rate_hz=metrics_rate,
        )
        publisher.start()

    monitor = None
    if queue_monitor_interval > 0:
        monitor = QueueMonitor(
            {"entries": q, "batches": async_writer.pending_queue},
            interval_s=queue_monitor_interval,
        )
        monitor.start()

    # SIGTERM is how Kubernetes asks for shutdown, so it has to reach the
    # flush below rather than killing the process where it stands.
    shutdown = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())

    logger.info("Starting Kafka subscriber")
    try:
        # start() launches the subscriber's own threads and returns, so the
        # main thread parks here. Falling straight through would run the
        # shutdown below a second into the run.
        sub.start()
        shutdown.wait()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception:
        logger.exception("Kafka subscriber encountered fatal error")
        raise
    finally:
        if publisher is not None:
            publisher.stop()
        if monitor is not None:
            monitor.stop()
        async_writer.stop()


if __name__ == "__main__":
    cli()
