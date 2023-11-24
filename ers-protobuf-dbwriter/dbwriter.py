# @file dbwriter.py Writing ERS schemas info to PostgreSQL database
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import erskafka.ERSSubscriber as erssub
import ers.issue_pb2 as ersissue
from functools import partial
import psycopg2
import json
import click
import logging


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--subscriber-address', type=click.STRING, default="monkafka.cern.ch", help="address of the ERSSubscriber")
@click.option('--subscriber-port',    type=click.INT,    default=30092, help='port of the ERSSubscriber')       
@click.option('--subscriber-group',   type=click.STRING, default=None, help='group ID of the ERSSubscriber')
@click.option('--subscriber-timeout', type=click.INT,    default=500, help='timeout in ms used in the ERSSubscriber')

@click.option('--db-address',  required=True, type=click.STRING, help='address of the PostgreSQL db')
@click.option('--db-port',     required=True, type=click.STRING, help='port of the PostgreSQL db')
@click.option('--db-user',     required=True, type=click.STRING, help='user for login to the PostgreSQL db')
@click.option('--db-password', required=True, type=click.STRING, help='password for login to the PostgreSQL db')
@click.option('--db-name',     required=True, type=click.STRING, help='name of the PostgreSQL db')
@click.option('--db-table',    required=True, type=click.STRING, help='name of table used in the PostgreSQL db')

@click.option('--debug',       type=click.BOOL, default=True, help='Set debug print levels')


def process_chain( chain, cursor, connection ) :
    logging.debug(chain)
    try :
        for cause in reversed(chain.causes) :
            process_issue(issue=cause, 
                          session=chain.session,
                          cursor=cursor)
        
        process_issue(issue=chain.final, 
                      session=chain.session,
                      cursor=cursor)

        connection.commit()
    except psycopg2.errors.UndefinedTable:
        connection.rollback()
        create_database(cursor=cursor,
                        connection=connection)
    except psycopg2.errors.UndefinedColumn:
        connection.rollback()
        clean_database(cursor=cursor, 
                       connection=connection)
        create_database(cursor=cursor,
                        connection=connection)
    except Exception as e:
        logging.error(e)
        

def process_issue( issue, session, cursor ) :
    fields = []
    values = []

    ## top level info
    add_entry("session", session, fields, values)
    add_entry("issue_name", issue.name, fields, values)
    add_entry("severity", issue.severity, fields, values)
    add_entry("time", issue.time, fields, values)

    ## context related info
    add_entry("cwd", issue.context.cwd, fields, values)
    add_entry("file_name", issue.context.file_name, fields, values)
    add_entry("function_name", issue.context.function_name, fields, values)
    add_entry("host_name", issue.context.host_name, fields, values)
    add_entry("line_number", issue.context.line_number, fields, values)
    add_entry("package_name", issue.context.package_name, fields, values)

    add_entry("process_id", issue.context.process_id, fields, values)
    add_entry("thread_id", issue.context.thread_id, fields, values)
    add_entry("user_id", issue.context.user_id, fields, values)
    add_entry("user_name", issue.context.user_name, fields, values)
    add_entry("application_name", issue.context.application_name, fields, values)

    # heavy information
    add_entry("inheritance", '/'.join(issue.inheritance), fields, values)
    add_entry("message", issue.message, fields, values)
    add_entry("params", str(issue.parameters), fields, values)
    

    command = "INSERT INTO public." + table_name;
    command += " (" + ", ".join(fields) + ')'
    command += " VALUES " + repr(tuple(values)) + ';'

    logging.debug(command)
    cursor.execute(command)
    
    
def add_entry(field, value, fields, values):
    fields.append(field)
    values.append(value)


def clean_database(cursor, connection):
    command = "DROP TABLE public."
    command += table_name
    command += ";"

    cursor.execute(command)
    connection.commit()
    

def create_database(cursor, connection):
    command = "CREATE TABLE public." + table_name + " ("
    command += '''
                session             TEXT, 
                issue_name          TEXT,
                inheritance         TEXT,
                message             TEXT,
                severity            TEXT,
                time                BIGINT,
                params              TEXT,
                cwd                 TEXT,
                file_name           TEXT,
                function_name       TEXT,
                host_name           TEXT,
                package_name        TEXT,
                user_name           TEXT,
                application_name    TEXT,
                user_id             INT,
                process_id          INT,
                thread_id           INT,
                line_number         INT
               ); ''' 

    cursor.execute(command)
    connection.commit()

def cli(subscriber_address, subscriber_port, subscriber_group, subscriber_timeout,
        db_address, db_port, db_user, db_password, db_name,
        db_table,
        debug):

    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG if debug else logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S')

    try:
        con = psycopg2.connect(host=db_address,
                              port=db_port,
                              user=db_user,
                              password=db_password,
                              dbname=db_name)
    except:
        logging.fatal('Connection to the database failed, aborting...')
        exit()

    global table_name
    table_name = '"' + db_table + '"'

    cur = con.cursor()

    try: # try to make sure tables exist
        create_database(cursor=cur, connection=con)
    except:
        con.rollback()
        logging.info( "Database was already created" )
    else :
        logging.info( "Database creation: Success" )
    finally:
        logging.info( "Database is ready" )

    kafka_bootstrap   = "{}:{}".format(subscriber_address, subscriber_port)

    subscriber_conf = json.loads("{}")
    subscriber_conf["bootstrap"] = kafka_bootstrap
    subscriber_conf["timeout"]   = subscriber_timeout
    subscriber_conf["group_id"]  = subscriber_group

    sub = erssub.ERSSubscriber(subscriber_conf)

    callback_function = partial(process_chain, 
                                cursor=cur, 
                                connection=con)
    
    sub.add_callback(name="postgres", 
                     function=callback_function)
    
    sub.start()


if __name__ == '__main__':
    cli(show_default=True, standalone_mode=True)

