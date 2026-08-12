"""OpMon entries to TimescaleDB writer.

This service subscribes to OpMon entries on Kafka, transforms them,
batches them, and writes them to TimescaleDB with automatic schema
management and Kubernetes health probes.

This is part of the DUNE DAQ software, copyright 2020.
Licensing/copyright details are in the COPYING file that you should have
received with this code.
"""

import logging
import queue
import threading

import click
import kafkaopmon.OpMonSubscriber as opmon_sub

from health_server import HealthServer
from timescale import BatchConsumer, Entry, OpMonTransformer, TimescaleWriter

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

# Default configuration values
DEFAULT_BOOTSTRAP_SERVER = "monkafka.cern.ch:30092"
DEFAULT_SUBSCRIBER_TIMEOUT_MS = 500
DEFAULT_DB_URI = "postgres://localhost:5432/test_timescaledb"
DEFAULT_BATCH_TIMEOUT_MS = 500

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
    health_port: int | None,
    debug: bool,
) -> None:
    """Run OpMon to TimescaleDB writer service.

    Subscribes to Kafka topics, transforms OpMon protobuf entries,
    batches them, and writes to TimescaleDB.
    """
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Starting OpMon TimescaleDB writer")
    logger.debug(
        "Config: bootstrap=%s, topics=%s, batch_timeout_ms=%d",
        subscriber_bootstrap,
        subscriber_topic,
        timescaledb_timeout,
    )

    writer = TimescaleWriter(timescaledb_uri, create_if_missing=timescaledb_create)
    logger.info("Connected to TimescaleDB")

    if health_port is not None:
        HealthServer(health_port, writer.is_healthy).start()

    q: queue.Queue[Entry] = queue.Queue()
    sub = opmon_sub.OpMonSubscriber(
        bootstrap=subscriber_bootstrap,
        topics=subscriber_topic,
        group_id=subscriber_group,
        timeout_ms=subscriber_timeout,
    )

    transformer = OpMonTransformer(q)

    sub.add_callback(
        name="to_timescale_db",
        function=transformer.process_entry,
    )

    consumer = BatchConsumer(q, writer, timescaledb_timeout)
    threading.Thread(target=consumer.start, daemon=True).start()
    logger.info("Batch consumer thread started")

    logger.info("Starting Kafka subscriber")
    try:
        sub.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception:
        logger.exception("Kafka subscriber encountered fatal error")
        raise


if __name__ == "__main__":
    cli()
