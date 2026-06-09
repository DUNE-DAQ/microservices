# @file dbwriter.py Writing ERS schemas info to database using SQLAlchemy
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import json
import logging
import re
import sys
import time
from functools import partial

import click
import erskafka.ERSSubscriber as erssub
import google.protobuf.json_format as pb_json
import sqlalchemy
from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    inspect,
)
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from threading import Thread
except ImportError:
    HTTPServer = None

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
MAX_RETRIES = 3
logger = logging.getLogger(__name__)
engine = None

if HTTPServer is not None:

    class HealthHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            logger.debug("HTTP: %s", format % args)

        def do_GET(self):
            if self.path == "/ready":
                self.handle_ready()
            elif self.path == "/live":
                self.handle_live()
            else:
                self.send_response(404)
                self.end_headers()

        def handle_ready(self):
            status = {"database": "healthy"}
            all_healthy = True

            try:
                if engine is not None:
                    with engine.connect() as conn:
                        conn.execute(sqlalchemy.text("SELECT 1"))
            except Exception:
                status["database"] = "unreachable"
                all_healthy = False

            if all_healthy:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ready", **status}).encode())
            else:
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "not ready", **status}).encode())

        def handle_live(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "live"}).encode())

    health_server = None
    health_thread = None

    def start_health_server(port: int):
        global health_server, health_thread
        health_server = HTTPServer(("0.0.0.0", port), HealthHandler)
        health_thread = Thread(target=health_server.serve_forever, daemon=True)
        health_thread.start()
        logger.info("Health server started on port %d", port)

    def stop_health_server():
        global health_server
        if health_server:
            health_server.shutdown()


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--subscriber-bootstrap",
    type=click.STRING,
    default="monkafka.cern.ch:30092",
    help="bootstrap server and port of the ERSSubscriber",
)
@click.option(
    "--subscriber-group",
    type=click.STRING,
    default=None,
    help="group ID of the ERSSubscriber",
)
@click.option(
    "--subscriber-timeout",
    type=click.INT,
    default=500,
    help="timeout in ms used in the ERSSubscriber",
)
@click.option(
    "--db-uri",
    required=True,
    type=click.STRING,
    help="SQLAlchemy database URI (e.g., postgresql://user:pass@host:port/dbname)",
)
@click.option(
    "--db-table",
    required=True,
    type=click.STRING,
    help="name of table used in the database",
)
@click.option("--debug", type=click.BOOL, default=True, help="Set debug print levels")
@click.option(
    "--health-port",
    type=click.INT,
    default=None,
    help="Port for HTTP health endpoint (if not set, no health endpoint)",
)
def cli(
    subscriber_bootstrap,
    subscriber_group,
    subscriber_timeout,
    db_uri,
    db_table,
    debug,
    health_port,
):
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", db_table):
        logger.fatal("Invalid --db-table name; use letters/numbers/underscore only")
        sys.exit(2)

    metadata = MetaData()
    try:
        global engine
        engine = create_engine(
            db_uri,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        issues_table = create_database_table(metadata, db_table, engine)
    except SQLAlchemyError:
        logger.exception("Failed to connect to database")
        logger.fatal("Connection to the database failed, aborting...")
        sys.exit(1)

    check_tables(engine=engine)

    if health_port is not None:
        start_health_server(health_port)

    subscriber_conf = {}
    subscriber_conf["bootstrap"] = subscriber_bootstrap
    subscriber_conf["timeout"] = subscriber_timeout
    if subscriber_group:
        subscriber_conf["group_id"] = subscriber_group

    sub = erssub.ERSSubscriber(subscriber_conf)

    callback_function = partial(process_chain, engine=engine, issues_table=issues_table)

    sub.add_callback(name="database", function=callback_function)

    try:
        sub.start()
    finally:
        if health_port is not None:
            stop_health_server()


def process_chain(chain, engine, issues_table):
    """Process a chain of issues and persist to database with retry logic"""
    logger.debug(chain)

    table_recreated = False  # Track if we've already recreated the table

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with engine.connect() as connection:
                # Process all causes in reverse order
                for cause in reversed(chain.causes):
                    with connection.begin():
                        process_issue(
                            issue=cause,
                            session=chain.session,
                            connection=connection,
                            issues_table=issues_table,
                        )

                # Process final issue
                with connection.begin():
                    process_issue(
                        issue=chain.final,
                        session=chain.session,
                        connection=connection,
                        issues_table=issues_table,
                    )

            # Success - exit the retry loop
            logger.debug(f"Entry sent successfully after {attempt} attempt(s)")
            return True

        except ProgrammingError:
            # ProgrammingError covers missing tables/columns, schema issues
            logger.exception(f"Programming error on attempt {attempt}")

            if not table_recreated:
                logger.warning(
                    "Schema/table issue detected, recreating table (one-time)"
                )
                try:
                    clean_database(issues_table, engine)
                    issues_table.metadata.create_all(engine)
                    table_recreated = True
                    continue  # retry after recreation
                except Exception:
                    logger.exception("Failed to recreate table")
                    if attempt >= MAX_RETRIES:
                        logger.error(  # noqa:TRY400
                            "Failed to deliver issue after all retry attempts. Chain:\n%s",
                            pb_json.MessageToJson(chain),
                        )
                        raise
                    continue

            # Table already recreated → persistent schema problem
            logger.exception("Table already recreated, schema issue persists")
            if attempt >= MAX_RETRIES:
                logger.error(  # noqa:TRY400
                    "Failed to deliver issue after all retry attempts. Chain:\n%s",
                    pb_json.MessageToJson(chain),
                )
                raise

            # Exponential backoff for transient issues, but never a huge number
            time.sleep(min(0.5 * (2**attempt), 5.0))
            continue

        except OperationalError:
            # OperationalError covers connection issues, locks, timeouts
            logger.exception(f"Operational error on attempt {attempt}")

            if attempt >= MAX_RETRIES:
                logger.error(  # noqa:TRY400
                    "Failed to deliver issue after all retry attempts. Chain:\n%s",
                    pb_json.MessageToJson(chain),
                )
                raise

            # Exponential backoff for transient issues, but never a huge number
            time.sleep(min(0.5 * (2**attempt), 5.0))
            continue

        except SQLAlchemyError:
            # Catch-all for other SQLAlchemy errors
            logger.exception(f"SQLAlchemy error on attempt {attempt}")
            if attempt >= MAX_RETRIES:
                logger.error(  # noqa:TRY400
                    "Failed to deliver issue after all retry attempts. Chain:\n%s",
                    pb_json.MessageToJson(chain),
                )
                raise

            # Exponential backoff for transient issues, but never a huge number
            time.sleep(min(0.5 * (2**attempt), 5.0))
            continue

        except Exception:
            # Unexpected errors shouldn't be retried
            logger.exception(
                "Unexpected error on attempt %d\nFailed to deliver issue due to unexpected error\nChain:\n%s",
                attempt,
                pb_json.MessageToJson(chain),
            )
            # Do not backoff here!
            raise

    # This should never be reached due to the raise in MAX_RETRIES checks,
    # but include as a safety fallback
    logger.error("Failed to deliver issue after all retry attempts")
    logger.error(pb_json.MessageToJson(chain))
    raise RuntimeError("Failed to deliver issue after all retry attempts")


def process_issue(issue, session, connection, issues_table):
    values = {}

    ## top level info
    values["session"] = str(session)
    values["issue_name"] = str(issue.name)
    values["severity"] = str(issue.severity)
    values["time"] = issue.time

    ## context related info
    values["cwd"] = str(issue.context.cwd)
    values["file_name"] = str(issue.context.file_name)
    values["function_name"] = str(issue.context.function_name)
    values["host_name"] = str(issue.context.host_name)
    values["line_number"] = issue.context.line_number
    values["package_name"] = str(issue.context.package_name)

    values["process_id"] = issue.context.process_id
    values["thread_id"] = issue.context.thread_id
    values["user_id"] = issue.context.user_id
    values["user_name"] = str(issue.context.user_name)
    values["application_name"] = str(issue.context.application_name)

    # heavy information
    values["inheritance"] = "/".join(issue.inheritance)
    values["message"] = str(issue.message)
    values["params"] = str(issue.parameters)

    ins = issues_table.insert().values(**values)
    logger.debug(str(ins))
    connection.execute(ins)


def clean_database(issues_table, engine):
    issues_table.drop(engine, checkfirst=True)
    logger.debug(f"Dropped table {issues_table.name}")


def check_tables(engine):
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Tables: {tables}")
    return tables


def create_database_table(metadata, table_name, engine):
    issues_table = Table(
        table_name,
        metadata,
        Column("session", Text),
        Column("issue_name", Text),
        Column("inheritance", Text),
        Column("message", Text),
        Column("params", Text),
        Column("severity", Text),
        Column("time", BigInteger),
        Column("cwd", Text),
        Column("file_name", Text),
        Column("function_name", Text),
        Column("host_name", Text),
        Column("package_name", Text),
        Column("user_name", Text),
        Column("application_name", Text),
        Column("user_id", Integer),
        Column("process_id", Integer),
        Column("thread_id", Integer),
        Column("line_number", Integer),
    )

    metadata.create_all(engine, checkfirst=True)
    logger.info("Database is ready")
    logger.debug(f"Created table {table_name}")
    return issues_table


if __name__ == "__main__":
    cli()
