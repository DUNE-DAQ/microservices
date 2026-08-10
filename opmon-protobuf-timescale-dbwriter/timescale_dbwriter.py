# @file dbwriter.py Writing Opmon entries into TimescaleDB
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.

import json
from typing import Callable
import logging
import queue
import socket as _socket
import threading
from functools import partial
from threading import Thread
from urllib.parse import urlparse
from dataclasses import dataclass

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

# Types
type BatchList = list[dict[str, Entry]]

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

OPMON_TABLE_PREFIX = "opmon_entries_"

logger = logging.getLogger(__name__)

# ------- SCHEMA --------- #

def uri_to_db_name(uri: str):
    parsed_uri = urlparse(uri)
    return parsed_uri.path.lstrip("/")


# ------- Opmon Processing -------- #
@dataclass
class Entry:
    """Encodify opmon entry
    """
    json: dict
    ms: int

def process_entry(entry: opmon_schema.OpMonEntry, q: queue.Queue):
    """Process opmon entry into Entry class
    """
    d = to_dict(entry)
    e = Entry(json=d, ms=entry.time.ToMilliseconds())
    q.put(e)

def to_dict(entry: opmon_schema.OpMonEntry) -> dict:
    """Convert OmponEntry into Entry class
    """
    ret = dict(measurement=entry.measurement)
    ret["fields"] = unpack_payload(entry)
    ret["tags"] = create_tags(entry)
    # Convert Protobuf Timestamp directly to Python datetime
    ret["time"] = entry.time.ToDatetime()
    return ret


def unpack_payload(entry: opmon_schema.OpMonEntry) -> dict:
    """Unpack OmponEntry
    """
    data = entry.data
    ret = dict()
    for key, value in data.items():
        kind = value.WhichOneof("kind")
        if kind is not None:
            ret[key] = getattr(value, kind)
    return ret


def create_tags(entry: opmon_schema.OpMonEntry) -> dict:
    """Generate DB tags
    """
    opmon_id = entry.origin
    tags = dict(session=opmon_id.session, application=opmon_id.application)

    struct = opmon_id.substructure
    for i, s in enumerate(struct):
        name = "sub" * i + "element"
        tags[name] = s

    tags.update(entry.custom_origin)
    return tags


# --- Health Client Tools --- #
class HealthServer:
    """Monitor database health"""
    def __init__(self, port: int, health_check: Callable[[], bool]):
        """Constructor"""
        self.port = port
        self._health_check = health_check
        self._sock: _socket.socket | None = None

    def start(self) -> None:
        """Start health server"""
        self._sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        self._sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", self.port))
        self._sock.listen(10)
        Thread(target=self._accept_loop, daemon=True).start()
        logger.info("Health server started on port %d", self.port)

    def stop(self) -> None:
        """Kill health server"""
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _accept_loop(self) -> None:
        """Health server acceptance loop
        """
        assert self._sock is not None

        while True:
            try:
                conn, _ = self._sock.accept()
                Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except OSError:
                break

    def _handle_client(self, conn: _socket.socket) -> None:
        """Handle client
        """
        try:
            data = b""
            conn.settimeout(5)
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk

            if b"GET /ready" in data:
                healthy = self._health_check()
                code, phrase = (200, "OK") if healthy else (503, "Service Unavailable")
                body = json.dumps({
                    "status": "ready" if healthy else "not ready",
                    "timescaledb": "healthy" if healthy else "unreachable",
                }).encode()
            elif b"GET /live" in data:
                code, phrase = 200, "OK"
                body = json.dumps({"status": "live"}).encode()
            else:
                code, phrase = 404, "Not Found"
                body = b"Not Found"

            response = (
                f"HTTP/1.0 {code} {phrase}\r\nContent-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n\r\n"
            ).encode() + body
            conn.sendall(response)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

# ------- DB Connection Tools ------ #
class TimescaleWriter():
    def __init__(self, uri: str, create_if_missing: bool):
        """Constructor"""
        self.engine = self._connect(uri, create_if_missing)
        self.metadata = MetaData()
        self._tables_lock = threading.Lock()

    def is_healthy(self) -> bool:
        """Is the server alive + kicking?
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except OperationalError:
            return False

    def _connect(self, uri: str, create_if_missing: bool) -> Engine:
        """Create engine"""
        db_name = uri_to_db_name(uri)
        if not db_name:
            raise ValueError("No database name in URI")

        engine = create_engine(uri)

        if database_exists(engine.url):
            return engine

        if not create_if_missing:
            raise ValueError("Cannot find DB %s", uri)

        create_database(engine.url)
        return engine

    def send_batch(self, batch: dict[str, BatchList]):
        """Send batch of entries
        """
        if self.engine is None:
            print(batch)

        if not len(batch):
            return

        total_points = sum(len(v) for v in batch.values())
        logger.info("Sending %s points across %s measurements", total_points, len(batch))

        try:
            tables = self._generate_batch_tables(list(batch.keys()))
            with self.engine.begin() as conn:
                for t, b in zip(tables, batch.values()):
                    conn.execute(t.insert(), b)
        except OperationalError:
            logger.exception("TimescaleDB connection error occurred")
        except SQLAlchemyError:
            logger.exception("Something went wrong: batch not sent")

    def _table_schema(self, table_name: str):
        """Generate a table with fixed schema"""
        return Table(
            table_name,
            self.metadata,
            Column("time", DateTime(timezone=True)),
            Column("measurement", Text),
            Column("tags", JSON),
            Column("fields", JSON),
            Index(f"ix_{table_name}_tags_gin", "tags", postgresql_using="gin"),
            Index(f"ix_{table_name}_fields_gin", "fields", postgresql_using="gin"),
        )

    def _find_or_create_table(self, measurement: str)->Table:
        """Create table"""
        # Finds table in the metadata OR create a new one
        table_name =  f"{OPMON_TABLE_PREFIX}{measurement}"
        # Prevent re-defining an existing table in metadata
        if table_name in self.metadata.tables:
            return self.metadata.tables[table_name]

        t = self._table_schema(table_name)
        t.create(self.engine, checkfirst=True)
        return t


    def _generate_batch_tables(self, measurements: list[str]):
        with self._tables_lock:
            return [self._find_or_create_table(m) for m in measurements]

    def consume(self, q: queue.Queue, timeout_ms: int):
        logger.info("Starting consumer thread")
        batch = {}
        batch_ms = 0

        while True:
            try:
                entry = q.get(timeout=1.0)

                if entry.ms - batch_ms < timeout_ms:
                    measure = entry.json["measurement"]
                    batch.setdefault(measure, []).append(entry.json)


                if entry.ms - batch_ms >= timeout_ms:
                    self.send_batch(batch)
                    batch = {entry.json["measurement"]: [entry]}
                    batch_ms = entry.ms

            except queue.Empty:
                logger.debug("Queue is empty")
                self.send_batch(batch)
                batch = {}
                batch_ms = 0


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

    writer = TimescaleWriter(timescaledb_uri, timescaledb_create)

    if health_port is not None:
        HealthServer(health_port, health_check=writer.is_healthy).start()

    q = queue.Queue()
    sub = opmon_sub.OpMonSubscriber(
        bootstrap=subscriber_bootstrap,
        topics=subscriber_topic,
        group_id=subscriber_group,
        timeout_ms=subscriber_timeout,
    )
    sub.add_callback(name="to_timescale_db", function=partial(process_entry, q=q))

    threading.Thread(
        target=writer.consume, daemon=True, args=(q, timescaledb_timeout)
    ).start()

    sub.start()


if __name__ == "__main__":
    cli()