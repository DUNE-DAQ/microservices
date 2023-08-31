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
import os


cursor = None
connection = None

def process_chain( chain ) :
    try :
        for cause in reversed(chain.causes) :
            process_issue(issue=cause, 
                          session=chain.session)
        
        process_issue( issue = chain.final, 
                       session = chain.session)

        global connection
        ##connection.commit()
    except psycopg2.errors.UndefinedTable:
        connection.rollback()
        create_database()
    except psycopg2.errors.UndefinedColumn:
        connection.rollback()
        clean_database()
        create_database()
    except Exception as e:
        print(e)
        

def process_issue( issue, session ) :
    fields = []
    values = []

    add_entry("session", session, fields, values)
    add_entry("issue_name", issue.name, fields, values)

    command = "INSERT INTO public." + table_name;
    command += " (" + ", ".join(fields) + ')'
    command += " VALUES " + repr(tuple(values)) + ';'

    global cursor
    ##cursor.execute(command)
    
    print(command)

def add_entry(field, value, fields, values):
    fields.append(field)
    values.append(value)


def clean_database():
    ## add table name variable
    command = "DROP TABLE public."
    command += table_name
    command += ";"

    global cursor
    ##cursor.execute(command)

    global connection
    ##connection.commit()
    
    print(command)


def create_database():
    ## make table name a variable
    command = "CREATE TABLE public." + table_name + " ("
    command += '''
                session             TEXT, 
                issue_name          TEXT,
                message             TEXT,
                severity            TEXT,
                time                BIGINT,
                qualifiers          TEXT,
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

    global cursor
    ##cursor.execute(command)

    global connection
    ##connection.commit()

    print(command)

def main():

#    host = os.environ['ERS_DBWRITER_HOST']
#    port = os.environ['ERS_DBWRITER_PORT']
#    user = os.environ['ERS_DBWRITER_USER']
#    password = os.environ['ERS_DBWRITER_PASS']
#    dbname = os.environ['ERS_DBWRITER_NAME']

#    try:
#        con = psycopg2.connect(host=host,
#                               port=port,
#                               user=user,
#                               password=password,
#                               dbname=dbname)
#    except:
#        print('Connection to the database failed, aborting...')
#        exit()

    global table_name
    table_name = '"' + "ERSTest" + '"' # os.environ['TABLE_NAME']

#    cur = con.cursor()

    try: # try to make sure tables exist
        create_database()
    except:
        # if this errors out it may be because the database is already there
        pass
    else :
        print( "Database creation: Success" )
    finally:
        print( "Databased created" )

    kafka_bootstrap = "monkafka.cern.ch:30092" # os.environ['KAFKA_BOOTSTRAP']
    kafka_timeout_ms   = 500                   # os.environ['KAFKA_TIMEOUT_MS'] 

    subscriber_conf = json.loads("{}")
    subscriber_conf["bootstrap"] = kafka_bootstrap
    subscriber_conf["timeout"]   = kafka_timeout_ms
    subscriber_conf["group_id"]  = "ers_microservice"

    sub = erssub.ERSSubscriber(subscriber_conf)

    sub.add_callback(name="postgres", 
                     function=process_chain)
    
    sub.start()


if __name__ == '__main__':
    main()
