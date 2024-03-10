# @file dbwriter.py Writing ERS schemas info to PostgreSQL database
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import erskafka.ERSSubscriber as erssub
import ers.issue_pb2 as ersissue
import google.protobuf.json_format as pb_json
from functools import partial
import psycopg2
import json
import click
import logging


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--subscriber-bootstrap', type=click.STRING, default="monkafka.cern.ch:30092", help="boostrap server and port of the ERSSubscriber")
@click.option('--subscriber-group',   type=click.STRING, default=None, help='group ID of the ERSSubscriber')
@click.option('--subscriber-timeout', type=click.INT,    default=500, help='timeout in ms used in the ERSSubscriber')

@click.option('--db-address',  required=True, type=click.STRING, help='address of the PostgreSQL db')
@click.option('--db-port',     required=True, type=click.STRING, help='port of the PostgreSQL db')
@click.option('--db-user',     required=True, type=click.STRING, help='user for login to the PostgreSQL db')
@click.option('--db-password', required=True, type=click.STRING, help='password for login to the PostgreSQL db')
@click.option('--db-name',     required=True, type=click.STRING, help='name of the PostgreSQL db')
@click.option('--db-table',    required=True, type=click.STRING, help='name of table used in the PostgreSQL db')

@click.option('--debug',       type=click.BOOL, default=True, help='Set debug print levels')

def cli(subscriber_bootstrap, subscriber_group, subscriber_timeout,
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
    except Exception as e:
        logging.error(e)
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

    check_tables(cursor=cur, connection=con)
        
    subscriber_conf = json.loads("{}")
    subscriber_conf["bootstrap"] = subscriber_bootstrap
    subscriber_conf["timeout"]   = subscriber_timeout
    if subscriber_group:
        subscriber_conf["group_id"]  = subscriber_group

    sub = erssub.ERSSubscriber(subscriber_conf)

    callback_function = partial(process_chain, 
                                cursor=cur, 
                                connection=con)
    
    sub.add_callback(name="postgres", 
                     function=callback_function)
    
    sub.start()


def process_chain( chain, cursor, connection ) :
    logging.debug(chain)

    counter = 0;
    success = False
    while(not success) :
        counter += 1
        try :
            for cause in reversed(chain.causes) :
                process_issue(issue=cause, 
                              session=chain.session,
                              cursor=cursor)

            process_issue(issue=chain.final, 
                          session=chain.session,
                          cursor=cursor)
            connection.commit()
        except psycopg2.errors.UndefinedTable as e:
       	    logging.error(e)
            logging.error("Table was undefined yet it was supposed to be defined at this point")
            connection.rollback()
            create_database(cursor=cursor,
                            connection=connection)
        except psycopg2.errors.UndefinedColumn as e:
            logging.warning(e)
            connection.rollback()
            clean_database(cursor=cursor, 
                           connection=connection)
            create_database(cursor=cursor,
                            connection=connection)
        except Exception as e:
            logging.error("Something unexpected happened")
            logging.error(e)

        else:
            success=True
            logging.debug(f"Entry sent after {counter} attempts")

        if (counter > 2) :
            if not success :
                logging.error("Issue failed to be delivered")
                logging.error(pb_json.MessageToJson(chain))
            break
        

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
    add_entry("params", issue.parameters, fields, values)

    command = f"INSERT INTO {table_name} ({','.join(fields)}) VALUES ({('%s, ' * len(values))[:-2]});"
   
    logging.debug(command)
    cursor.execute(command, values)


def add_entry(field, value, fields, values):
    fields.append(field)
    values.append(str(value))


def clean_database(cursor, connection):
    command = f"DROP TABLE {table_name} ;"

    logging.debug(command)
    cursor.execute(command)
    connection.commit()

def check_tables(cursor, connection) :
    command = """SELECT relname FROM pg_class WHERE relkind='r'
                  AND relname !~ '^(pg_|sql_)';"""
    
    logging.debug(command)
    cursor.execute(command)
    tables = [i[0] for i in cursor.fetchall()] # A list() of tables.
    logging.info(f"Tables: {tables}")
    return tables

def create_database(cursor, connection):
    command = f"CREATE TABLE {table_name} ("
    command += '''
                session             TEXT, 
                issue_name          TEXT,
                inheritance         TEXT,
                message             TEXT,
                params              TEXT,
                severity            TEXT,
                time                BIGINT,
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

    logging.debug(command)
    cursor.execute(command)
    connection.commit()



if __name__ == '__main__':
    cli()

