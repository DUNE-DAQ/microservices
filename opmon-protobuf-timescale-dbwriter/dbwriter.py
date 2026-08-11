# @file dbwriter.py Writing Opmon entries into TimescaleDB
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.

import logging
import queue
import threading

import click
import kafkaopmon.OpMonSubscriber as opmon_sub
from flask import Flask
from health_server import HealthServer
from timescale import BatchConsumer, OpMonTransformer, TimescaleWriter

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

logger = logging.getLogger(__name__)

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
    default="postgres://localhost:5432/test_timescaledb",
    help="URI of the timescaleDB server (e.g., postgres]://user:pass@host:port/dbname)",
)
@click.option(
    "--timescaledb_create",
    type=click.BOOL,
    default=True,
    help="Creates the timescaledb if it does not exist",
)
@click.option(
    "--timescaledb_timeout",
    type=click.INT,
    default=500,
    help="Size in ms of the batches sent to timescale",
)
@click.option(
    "--health-port",
    type=click.INT,
    default=None,
    help="Port for HTTP health endpoint (if not set, no health endpoint)",
)
@click.option("--debug", type=click.BOOL, default=True, help="Set debug print levels")
def cli( # noqa: PLR0913
    subscriber_bootstrap,
    subscriber_group,
    subscriber_timeout,
    subscriber_topic,
    timescaledb_uri,
    timescaledb_create,
    timescaledb_timeout,
    health_port,
    debug,
):
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    writer = TimescaleWriter(timescaledb_uri, create_if_missing=timescaledb_create)

    if health_port is not None:
        HealthServer(health_port, writer.is_healthy).start()

    q = queue.Queue()
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

    sub.start()


if __name__ == "__main__":
    cli()
