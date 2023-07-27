# @file dbwriter.py Writing ERS schemas info to PostgreSQL database
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import erskafka.ERSSubscriber as erssub
import ers.issue_pb2 as ersissue
import google.protobuf.json_format as pb_json
#from functools import partial
import psycopg2
import json
import os


def process_chain( issue ) :

    for cause in reversed(issue.causes) :
        process_issue(issue=cause, 
                      session=issue.session)
        
    process_issue( issue = issue.final, 
                   session = issue.session)
    

def process_issue( issue, session ) :
    fields = []
    values = []



##    try:
##        cur.execute(f'INSERT INTO public."ErrorReports" ({",".join(fields)}) VALUES({("%s, " * len(ls))[:-2]})', ls)
##        # Save the insert (or any change) to the database
##        con.commit()
##    except psycopg2.errors.UndefinedTable:
##        con.rollback()
##        create_database(cur, con)
##    except psycopg2.errors.UndefinedColumn:
##        con.rollback()
##        clean_database(cur, con)
##        create_database(cur, con)



def clean_database(cursor, connection):
    ## add table name variable
    cursor.execute('''
                DROP TABLE public."ErrorReports";
                ''')
    connection.commit()

def create_database(cursor, connection):
    ## make table name a variable
    cursor.execute('''
                CREATE TABLE public."ErrorReports" (
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
               );
               '''
                )
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

    global table_name = "ERSTest"  # os.environ['TABLE_NAME']

    # These are the fields in the ERS messages, see erskafka/src/KafkaStream.cpp
    fields = ["partition", "issue_name", "message", "severity", "usecs_since_epoch", "time",
              "qualifiers", "params", "cwd", "file_name", "function_name", "host_name",
              "package_name", "user_name", "application_name", "user_id", "process_id",
              "thread_id", "line_number", "chain"]

    cur = con.cursor()

    try: # try to make sure tables exist
        create_database(cur, con)
    except:
        # if this errors out it may be because the database is already there
        pass

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
