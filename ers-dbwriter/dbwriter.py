# @file dbwriter.py Writing ERS info to PostgreSQL database
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

from kafka import KafkaConsumer
import psycopg2
import json
import os

def clean_database(cursor, connection):
    cursor.execute('''
                DROP TABLE public."ErrorReports";
                ''')
    connection.commit()

def create_database(cursor, connection):
    cursor.execute('''
                CREATE TABLE public."ErrorReports" (
                partition           TEXT,
                issue_name          TEXT,
                message             TEXT,
                severity            TEXT,
                usecs_since_epoch   BIGINT,
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
                line_number         INT,
                chain               TEXT
               );
               '''
                )
    connection.commit()

def main():
    kafka_host = os.environ['ERS_DBWRITER_KAFKA_HOST']
    kafka_port = os.environ['ERS_DBWRITER_KAFKA_PORT']

    try:
        consumer = KafkaConsumer(
            'erskafka-reporting',
            bootstrap_servers=f'{kafka_host}:{kafka_port}',
            group_id='group1'
        )
    except:
        print('Connection to the kafka failed, aborting...')
        exit()

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
        print('Connection to the postgres database failed, aborting...')
        exit()

    # These are the fields in the ERS messages, see erskafka/src/KafkaStream.cpp
    fields = ["partition", "issue_name", "message", "severity", "usecs_since_epoch", "time",
              "qualifiers", "params", "cwd", "file_name", "function_name", "host_name",
              "package_name", "user_name", "application_name", "user_id", "process_id",
              "thread_id", "line_number", "chain"]

    cur = con.cursor()

    # Infinite loop over the kafka messages
    for message in consumer:
        print(message)
        js = json.loads(message.value)
        if js == '[]':
            continue
        ls = [str(js[key]) for key in fields]

        try:
            cur.execute(f'INSERT INTO public."ErrorReports" ({",".join(fields)}) VALUES({("%s, " * len(ls))[:-2]})', ls)
            # Save the insert (or any change) to the database
            con.commit()
        except psycopg2.errors.UndefinedTable:
            con.rollback()
            create_database(cur, con)
        except psycopg2.errors.UndefinedColumn:
            con.rollback()
            clean_database(cur, con)
            create_database(cur, con)

if __name__ == '__main__':
    main()
