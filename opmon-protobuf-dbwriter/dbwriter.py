# @file dbwriter.py Writing Opmon entries into InfluxDB
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import kafkaopmon.OpMonSubscriber as opmon_sub
import google.protobuf.json_format as pb_json
from google.protobuf.timestamp_pb2 import Timestamp
import opmonlib.opmon_entry_pb2 as opmon_schema

from influxdb import InfluxDBClient
import influxdb
from functools import partial
import json
import click
import logging
import queue
import threading


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS)
# subscriber options
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
# influx options
@click.option(
    "--influxdb-address",
    type=click.STRING,
    default="monkafka.cern.ch",
    help="address of the influx db",
)
@click.option(
    "--influxdb-port", type=click.INT, default=31002, help="port of the influxdb"
)
@click.option(
    "--influxdb-name",
    type=click.STRING,
    default="test_influx",
    help="Table name destination inside influxdb",
)
@click.option(
    "--influxdb-create",
    type=click.BOOL,
    default=True,
    help="Creates the influxdb if it does not exists",
)
@click.option(
    "--influxdb-timeout",
    type=click.INT,
    default=500,
    help="Size in ms of the batches sent to influx",
)
@click.option(
    "--influxdb-username",
    type=click.STRING,
    default=None,
    help="Username to acces influxdb",
)
@click.option(
    "--influxdb-password",
    type=click.STRING,
    default=None,
    help="Password to acces influxdb",
)
@click.option("--debug", type=click.BOOL, default=True, help="Set debug print levels")
def cli(
    subscriber_bootstrap,
    subscriber_group,
    subscriber_timeout,
    subscriber_topic,
    influxdb_address,
    influxdb_port,
    influxdb_name,
    influxdb_create,
    influxdb_timeout,
    influxdb_username,
    influxdb_password,
    debug,
):
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    kwargs = dict()
    if influxdb_username:
        kwargs["username"] = influxdb_username
    if influxdb_password:
        kwargs["password"] = influxdb_password
    influx = InfluxDBClient(host=influxdb_address, port=influxdb_port, **kwargs)
    db_list = influx.get_list_database()
    logging.info("Available DBs: %s", db_list)
    if {"name": influxdb_name} not in db_list:
        logging.warning("%s DB not available", influxdb_name)
        if influxdb_create:
            influx.create_database(influxdb_name)
            logging.info("New list of DBs: %s", influx.get_list_database())

    influx.switch_database(influxdb_name)

    sub = opmon_sub.OpMonSubscriber(
        bootstrap=subscriber_bootstrap,
        topics=subscriber_topic,
        group_id=subscriber_group,
        timeout_ms=subscriber_timeout,
    )

    # this is a list of Entries
    q = queue.Queue()

    callback_function = partial(process_entry, q=q)

    sub.add_callback(name="to_influx", function=callback_function)

    thread = threading.Thread(
        target=consume, daemon=True, args=(q, influxdb_timeout, influx)
    )
    thread.start()

    sub.start()


def consume(q: queue.Queue, timeout_ms, influx: InfluxDBClient = None):
    logging.info("Starting consumer thread")
    batch = []
    batch_ms = 0
    while True:
        try:
            entry = q.get(timeout=1)  ## timeout here is in seconds

            if entry.ms - batch_ms < timeout_ms:
                # because of the if, batch_ms is not zero.
                batch.append(entry.json)
                batch_ms = min(batch_ms, entry.ms)

            if entry.ms - batch_ms >= timeout_ms:
                # note that if we are facing with a late arrival, i.e. entry.ms was smaller than batch_ms, the difference is 0, so this if is skipped
                # i.e. there is not double insertion
                send_batch(batch, influx)
                batch = [entry.json]
                batch_ms = entry.ms

        except queue.Empty:
            logging.debug("Queue is empty")
            send_batch(batch, influx)
            batch = []
            batch_ms = 0


def send_batch(batch: list, influx: InfluxDBClient = None):
    if len(batch) > 0:
        logging.info("Sending %s points", len(batch))
        if influx:
            try:
                influx.write_points(batch)
            except influxdb.exceptions.InfluxDBClientError as e:
                logging.error(e)
            except Exception as e:
                logging.error("Something went wrong: json batch not sent")
                logging.error("Details: {}".format(str(e)))
        else:
            print(batch)


def process_entry(entry: opmon_schema.OpMonEntry, q: queue.Queue):
    d = to_dict(entry)
    e = Entry(json=d, ms=entry.time.ToMilliseconds())
    q.put(e)


def to_dict(entry: opmon_schema.OpMonEntry) -> dict:
    ret = dict(measurement=entry.measurement)
    ret["fields"] = unpack_payload(entry)
    ret["tags"] = create_tags(entry)
    ret["time"] = entry.time.ToJsonString()
    return ret


def unpack_payload(entry: opmon_schema.OpMonEntry) -> dict:
    data = entry.data
    ret = dict()
    for key in data:
        value = data[key]
        casted_value = getattr(value, value.WhichOneof("kind"))
        ret[key] = casted_value

    return ret


def create_tags(entry: opmon_schema.OpMonEntry) -> dict:
    opmon_id = entry.origin
    # session and application
    tags = dict(session=opmon_id.session, application=opmon_id.application)

    # element and subelements
    struct = opmon_id.substructure
    for i in range(len(struct)):
        name = "sub" * i + "element"
        tags[name] = struct[i]

    # custom origin
    tags |= entry.custom_origin

    return tags


class Entry:
    def __init__(self, json: dict, ms: int):
        self.json = json
        self.ms = ms


if __name__ == "__main__":
    cli()
