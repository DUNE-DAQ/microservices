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
import os


def process_chain( chain, cursor, connection ) :
    print(chain)
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
        print(e)
        

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

    print(command)
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

def main():

    host = os.environ['ERS_DBWRITER_HOST']
    port = os.environ['ERS_DBWRITER_PORT']
    user = os.environ['ERS_DBWRITER_USER']
    password = os.environ['ERS_DBWRITER_PASS']
    dbname = os.environ['ERS_DBWRITER_NAME']

    try:
        con = psycopg2.connect(host=host,
                              port=port,
                              user=user,
                              password=password,
                              dbname=dbname)
    except:
        print('Connection to the database failed, aborting...')
        exit()

    global table_name
    table_name = '"' + os.environ['ERS_TABLE_NAME'] + '"'

    cur = con.cursor()

    try: # try to make sure tables exist
        create_database(cursor=cur, connection=con)
    except:
        con.rollback()
        print( "Database was already created" )
    else :
        print( "Database creation: Success" )
    finally:
        print( "Database is ready" )

    kafka_bootstrap   = os.environ['ERS_DBWRITER_KAFKA_BOOTSTRAP_SERVER']
    kafka_timeout_ms  = int(os.environ['ERS_DBWRITER_KAFKA_TIMEOUT_MS'])

    subscriber_conf = json.loads("{}")
    subscriber_conf["bootstrap"] = kafka_bootstrap
    subscriber_conf["timeout"]   = kafka_timeout_ms
    subscriber_conf["group_id"]  = os.environ['ERS_DBWRITER_KAFKA_GROUP']

    sub = erssub.ERSSubscriber(subscriber_conf)

    callback_function = partial(process_chain, 
                                cursor=cur, 
                                connection=con)
    
    sub.add_callback(name="postgres", 
                     function=callback_function)
    
    sub.start()


if __name__ == '__main__':
    main()
