# @file dbwriter.py Writing Opmon entries into TimescaleDB
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.

import json
import logging
import queue
import socket as _socket
import threading
from functools import partial
from threading import Thread
from urllib.parse import urlparse

import click
import kafkaopmon.OpMonSubscriber as opmon_sub
import opmonlib.opmon_entry_pb2 as opmon_schema

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Index,
    JSON,
    MetaData,
    Table,
    Text,
    create_engine,
    text,
)
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy_utils import create_database, database_exists

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

OPMON_TABLE_PREFIX = "opmon_entries_"

logger = logging.getLogger(__name__)
metadata = MetaData()
timescale_engine = None
_health_server_socket = None

_tables_lock = threading.Lock()

# ------- SCHEMA --------- #
def _table_name_from_measurement(measurement: str):
    return f"{OPMON_TABLE_PREFIX}{measurement}"

def _table_schema(table_name: str):
    return Table(
        table_name,
        metadata,
        Column("time", DateTime(timezone=True)),
        Column("measurement", Text),
        Column("tags", JSON),
        Column("fields", JSON),    
        Index(f"ix_{table_name}_tags_gin", "tags", postgresql_using="gin"),
        Index(f"ix_{table_name}_fields_gin", "fields", postgresql_using="gin"),
    )


# ------- Opmon Processing -------- #
class Entry:
    def __init__(self, json_data: dict, ms: int):
        self.json = json_data
        self.ms = ms


def process_entry(entry: opmon_schema.OpMonEntry, q: queue.Queue):
    d = to_dict(entry)
    e = Entry(json_data=d, ms=entry.time.ToMilliseconds())
    q.put(e)


def to_dict(entry: opmon_schema.OpMonEntry) -> dict:
    ret = dict(measurement=entry.measurement)
    ret["fields"] = unpack_payload(entry)
    ret["tags"] = create_tags(entry)
    # Convert Protobuf Timestamp directly to Python datetime
    ret["time"] = entry.time.ToDatetime()
    return ret


def unpack_payload(entry: opmon_schema.OpMonEntry) -> dict:
    data = entry.data
    ret = dict()
    for key, value in data.items():
        kind = value.WhichOneof("kind")
        if kind is not None:
            ret[key] = getattr(value, kind)
    return ret


def create_tags(entry: opmon_schema.OpMonEntry) -> dict:
    opmon_id = entry.origin
    tags = dict(session=opmon_id.session, application=opmon_id.application)

    struct = opmon_id.substructure
    for i, s in enumerate(struct):
        name = "sub" * i + "element"
        tags[name] = s

    tags.update(entry.custom_origin)
    return tags


# --- Health Client Tools --- #
def _handle_health_client(conn):
    try:
        data = b""
        conn.settimeout(5)
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk

        if b"GET /ready" in data:
            status = {"timescaledb": "healthy"}
            all_healthy = True
            try:
                if timescale_engine is not None:
                    with timescale_engine.connect() as conn2:
                        conn2.execute(text("SELECT 1"))
            except OperationalError:
                status["timescaledb"] = "unreachable"
                all_healthy = False
            code, phrase = (200, "OK") if all_healthy else (503, "Service Unavailable")
            body = json.dumps({"status": "ready" if all_healthy else "not ready", **status}).encode()
        elif b"GET /live" in data:
            code, phrase = 200, "OK"
            body = json.dumps({"status": "live"}).encode()
        else:
            code, phrase = 404, "Not Found"
            body = b"Not Found"

        response = (
            f"HTTP/1.0 {code} {phrase}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n"
        ).encode() + body
        conn.sendall(response)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _health_accept_loop(sock):
    while True:
        try:
            conn, _ = sock.accept()
            Thread(target=_handle_health_client, args=(conn,), daemon=True).start()
        except OSError:
            break


def start_health_server(port: int):
    global _health_server_socket
    _health_server_socket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    _health_server_socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    _health_server_socket.bind(("0.0.0.0", port))
    _health_server_socket.listen(10)
    Thread(target=_health_accept_loop, args=(_health_server_socket,), daemon=True).start()
    logger.info("Health server started on port %d", port)


# ------- DB Connection Tools ------ #
def uri_to_db_name(uri: str):
    parsed_uri = urlparse(uri)
    return parsed_uri.path.lstrip("/")


def _connect_timescale(timescaledb_uri: str, timescaledb_create: bool) -> Engine:
    db_name = uri_to_db_name(timescaledb_uri)
    if not db_name:
        raise ValueError("No database name in URI")

    engine = create_engine(timescaledb_uri)

    if database_exists(engine.url):
        return engine

    if not timescaledb_create:
        raise ValueError(f"Cannot find {db_name} DB")

    create_database(engine.url)
    return engine


def consume(q: queue.Queue, timeout_ms: int, timescale_db: Engine | None = None):
    logger.info("Starting consumer thread")
    batch = {}
    batch_start_ms = None

    while True:
        try:
            entry = q.get(timeout=1.0)
            now_ms = entry.ms

            if batch_start_ms is None:
                batch_start_ms = now_ms

            measure = entry.json["measurement"]
            batch.setdefault(measure, []).append(entry.json)

            if now_ms - batch_start_ms >= timeout_ms:
                send_batch(batch, timescale_db)
                batch = {}
                batch_start_ms = None

        except queue.Empty:
            if batch:
                send_batch(batch, timescale_db)
                batch = {}
                batch_start_ms = None


def _find_or_create_table(measurement: str, engine: Engine):
    # Finds table in the metadata OR create a new one
    table_name = _table_name_from_measurement(measurement)
    # Prevent re-defining an existing table in metadata
    if table_name in metadata.tables:
        return metadata.tables[table_name]

    t = _table_schema(table_name)
    t.create(engine, checkfirst=True)
    return t

def _generate_batch_tables(measurements: list[str], engine: Engine):
    with _tables_lock:
        return [_find_or_create_table(m, engine) for m in measurements]


def send_batch(batch: dict[str, list[dict]], engine: Engine | None = None):
    if len(batch) > 0:
        total_points = sum(len(v) for v in batch.values())
        logger.info("Sending %s points across %s measurements", total_points, len(batch))

        if engine is not None:
            tables = _generate_batch_tables(list(batch.keys()), engine)
            try:
                with engine.begin() as conn:
                    for t, b in zip(tables, batch.values()):
                        conn.execute(t.insert(), b)
            except OperationalError:
                logger.exception("TimescaleDB connection error occurred")
            except SQLAlchemyError:
                logger.exception("Something went wrong: batch not sent")
        else:
            print(batch)


# --------- CLI --------- #
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
# timescale options
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
    help="Port for HTTP health e ndpoint (if not set, no health endpoint)",
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

    global timescale_engine
    timescale_engine = _connect_timescale(timescaledb_uri, timescaledb_create)

    sub = opmon_sub.OpMonSubscriber(
        bootstrap=subscriber_bootstrap,
        topics=subscriber_topic,
        group_id=subscriber_group,
        timeout_ms=subscriber_timeout,
    )

    q = queue.Queue()

    callback_function = partial(process_entry, q=q)
    if health_port is not None:
        start_health_server(health_port)

    sub.add_callback(name="to_timescale_db", function=callback_function)

    thread = threading.Thread(
        target=consume, daemon=True, args=(q, timescaledb_timeout, timescale_engine)
    )
    thread.start()

    sub.start()


if __name__ == "__main__":
    cli()