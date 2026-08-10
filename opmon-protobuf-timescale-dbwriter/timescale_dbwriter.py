# @file dbwriter.py Writing Opmon entries into TimescaleDB
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.

import json
import logging
import queue
import threading
from functools import partial
from urllib.parse import urlparse

import click
import kafkaopmon.OpMonSubscriber as opmon_sub
import opmonlib.opmon_entry_pb2 as opmon_schema

from sqlalchemy import (Engine,
                        create_engine,
                        text,
                        MetaData,
                        Table,
                        Column,
                        DateTime,
                        JSON,
                        Text)

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from sqlalchemy_utils import database_exists, create_database

import socket as _socket
from threading import Thread

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

TABLE_SCHEMA = {"time": "TIMESTAMPTZ",
                "measurement": "TEXT",
                "tags": "JSONB",
                "fields": "JSONB"}
OPMON_TABLE_PREFIX = "opmon_entries_"


logger = logging.getLogger(__name__)
metadata = MetaData()
timescale_engine = None
_health_server_socket = None

_tables_cache = {}
_tables_lock = threading.Lock()


# ------- SCHEMA --------- #
def _table_schema(measurement: str):
    # Create table + schema definition
    table_name = f"{OPMON_TABLE_PREFIX}{measurement}"
    return Table(
        table_name,
        metadata,
        Column("time", DateTime(timezone=True)),
        Column("measurement", Text),
        Column("tags", JSON),
        Column("fields", JSON),
    )

# ------- Opmon Processing -------- #
class Entry:
    def __init__(self, json: dict, ms: int):
        self.json = json
        self.ms = ms

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
    for i, s in enumerate(struct):
        name = "sub" * i + "element"
        tags[name] = s

    # custom origin
    tags |= entry.custom_origin

    return tags

# --- Health Client Tools --- #
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

def _connect_timescale(timescaledb_uri: str, timescaledb_create: bool)->Engine:
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

def consume(q: queue.Queue, timeout_ms, timescale_db: Engine | None = None):
    logger.info("Starting consumer thread")
    batch = {}
    batch_ms = 0
    while True:
        try:
            entry = q.get(timeout=1)  ## timeout here is in seconds

            if entry.ms - batch_ms < timeout_ms:
                # because of the if, batch_ms is not zero.
                measure = entry.json['measurement']
                batch_measure = batch.get(measure, [])
                batch_measure.append(entry.json)
                batch[measure] = batch_measure
                batch_ms = min(batch_ms, entry.ms)

            if entry.ms - batch_ms >= timeout_ms:
                # note that if we are facing with a late arrival, i.e. entry.ms was smaller than batch_ms, the difference is 0, so this if is skipped
                # i.e. there is not double insertion
                send_batch(batch, timescale_db)
                batch[entry.json['measurement']] = entry.json
                batch_ms = entry.ms

        except queue.Empty:
            logger.debug("Queue is empty")
            send_batch(batch, timescale_db)
            batch = {}
            batch_ms = 0

def _find_or_create_table(measurement: str, engine: Engine):
    # Looks up table in cache, if not found generates a new table
    t = _tables_cache.get(measurement)
    if not t:
        t = _table_schema(measurement)
        t.create(engine, checkfirst=True)
        _tables_cache[measurement] = t
    return t

def _generate_batch_tables(measurements: list[str], engine: Engine):
    # Create tables for batch if they don't already exist
    with _tables_lock:
        return [_find_or_create_table(m, engine) for m in measurements]

def send_batch(batch: dict[str, dict], engine: Engine | None = None):
    
    if len(batch) > 0:
        logger.info("Sending %s points", len(batch))
        
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
