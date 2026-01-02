# @file dbwriter.py Writing ERS schemas info to database using SQLAlchemy
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import json
import logging
from functools import partial

import click
import erskafka.ERSSubscriber as erssub
import google.protobuf.json_format as pb_json
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
from sqlalchemy.exc import (
    OperationalError,
    SQLAlchemyError,
)

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])
MAX_RETRIES = 3


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--subscriber-bootstrap",
    type=click.STRING,
    default="monkafka.cern.ch:30092",
    help="boostrap server and port of the ERSSubscriber",
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
def cli(
    subscriber_bootstrap,
    subscriber_group,
    subscriber_timeout,
    db_uri,
    db_table,
    debug,
):

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        engine = create_engine(db_uri)
        engine.connect()
    except SQLAlchemyError:
        logging.exception("Failed to connect to database")
        logging.fatal("Connection to the database failed, aborting...")
        exit()

    metadata = MetaData()
    issues_table = create_database_table(metadata, db_table, engine)

    check_tables(engine=engine)

    subscriber_conf = json.loads("{}")
    subscriber_conf["bootstrap"] = subscriber_bootstrap
    subscriber_conf["timeout"] = subscriber_timeout
    if subscriber_group:
        subscriber_conf["group_id"] = subscriber_group

    sub = erssub.ERSSubscriber(subscriber_conf)

    callback_function = partial(process_chain, engine=engine, issues_table=issues_table)

    sub.add_callback(name="database", function=callback_function)

    sub.start()


def process_chain(chain, engine, issues_table):
    """Process a chain of issues and persist to database with retry logic"""
    logging.debug(chain)

    # Proactively ensure table exists
    inspector = inspect(engine)
    if issues_table.name not in inspector.get_table_names():
        logging.warning(f"Table {issues_table.name} doesn't exist, creating it")
        create_database_table(issues_table.metadata, issues_table.name, engine)

    for attempt in range(1, MAX_RETRIES + 1):
        connection = engine.connect()
        trans = connection.begin()

        try:
            # Process all causes in reverse order
            for cause in reversed(chain.causes):
                process_issue(
                    issue=cause,
                    session=chain.session,
                    connection=connection,
                    issues_table=issues_table,
                )

            # Process final issue
            process_issue(
                issue=chain.final,
                session=chain.session,
                connection=connection,
                issues_table=issues_table,
            )

            trans.commit()
            logging.debug(f"Entry sent successfully after {attempt} attempt(s)")
            return True

        except OperationalError:
            logging.exception(f"Operational error on attempt {attempt}")
            trans.rollback()

            # Check if table is missing
            inspector = inspect(engine)
            if issues_table.name not in inspector.get_table_names():
                logging.warning("Table missing, recreating")
                create_database_table(issues_table.metadata, issues_table.name, engine)
                continue

            # Handle schema mismatch - recreate table
            logging.warning("Possible schema issue detected, recreating table")
            clean_database(issues_table, engine)
            create_database_table(issues_table.metadata, issues_table.name, engine)

        except SQLAlchemyError:
            logging.exception(f"SQLAlchemy error on attempt {attempt}")
            trans.rollback()

            if attempt >= MAX_RETRIES:
                logging.error("Max retries reached, operation failed")
                raise

        except Exception:
            logging.exception(f"Unexpected error on attempt {attempt}")
            trans.rollback()

            if attempt >= MAX_RETRIES:
                logging.error("Max retries reached due to unexpected error")
                raise

        finally:
            connection.close()

    # If we get here, all retries failed
    logging.error("Failed to deliver issue after all retry attempts")
    logging.error(pb_json.MessageToJson(chain))
    return False


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
    logging.debug(str(ins))
    connection.execute(ins)


def clean_database(issues_table, engine):
    issues_table.drop(engine, checkfirst=True)
    logging.debug(f"Dropped table {issues_table.name}")


def check_tables(engine):
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logging.info(f"Tables: {tables}")
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
    logging.info("Database is ready")
    logging.debug(f"Created table {table_name}")
    return issues_table


if __name__ == "__main__":
    cli()
