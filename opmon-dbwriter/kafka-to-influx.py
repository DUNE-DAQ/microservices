#
# @file dbwriter.py Writing ERS info to PostgreSQL database
# This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

from kafka import KafkaConsumer
import psycopg2
import json
import click

@click.command()
@click.option('--kafka-broker', type=click.STRING, default='monkafka.cern.ch',
              help='address of the kafka broker')
@click.option('--kafka-port', type=click.INT, default=30092,
              help='port of the kafka broker')       
@click.option('--kafka-topics', default=['opmon'],
              help='topics of the kafka broker')
@click.option('--kafka-consumer-group', type=click.STRING, default='opmon_microservice',
              help='topics of the kafka broker')
@click.option('--influxdb-address', type=click.STRING, default='opmondb.cern.ch',
              help='address of the influx db')
@click.option('--influxdb-port', type=click.INT, default=31002,
              help='port of the influxdb')
@click.option('--influxdb-path', type=click.STRING, default='write',
              help='path used in the influxdb query')
@click.option('--influxdb-name', type=click.STRING, default='influxdb',
              help='name used in the influxdb query')

def cli(kakfa_broker, karkfa_port, kafka_topics, 
        influx_address, influx_port, influx_path, influx_name):

    consumer = KafkaConsumer('erskafka-reporting',
                            bootstrap_servers='monkafka.cern.ch:30092',
                            group_id='group1')

    # Get credentials, it expects a file with the following fields, each in a different line:

    # host
    # port
    # user
    # password
    # dbname

    with open(filename) as f:
        host, port, user, password, dbname = f.read().split('\n')

    try:
        con = psycopg2.connect(host=host,
                            port=port,
                            user=user,
                            password=password,
                            dbname=dbname)
    except:
        print('Connection to the database failed, aborting...')
        exit()

    # These are the fields in the ERS messages, see erskafka/src/KafkaStream.cpp
    fields = ["partition", "issue_name", "message", "severity", "usecs_since_epoch", "time",
            "qualifiers", "params", "cwd", "file_name", "function_name", "host_name",
            "package_name", "user_name", "application_name", "user_id", "process_id",
            "thread_id", "line_number", "chain"]

    cur = con.cursor()

    # Uncomment to clean the database
    # cur.execute('''
    #             DROP TABLE public."ErrorReports";
    #             ''')
    # con.commit()
    # exit()

    # Uncomment to create the table used for the database
    # cur.execute('''
    #             CREATE TABLE public."ErrorReports" (
    #             partition           TEXT,
    #             issue_name          TEXT,
    #             message             TEXT,
    #             severity            TEXT,
    #             usecs_since_epoch   BIGINT,
    #             time                BIGINT,
    #             qualifiers          TEXT,
    #             params              TEXT,
    #             cwd                 TEXT,
    #             file_name           TEXT,
    #             function_name       TEXT,
    #             host_name           TEXT,
    #             package_name        TEXT,
    #             user_name           TEXT,
    #             application_name    TEXT,
    #             user_id             INT,
    #             process_id          INT,
    #             thread_id           INT,
    #             line_number         INT,
    #             chain               TEXT
    #            );
    #            '''
    #             )
    # con.commit()
    # exit()

    # Infinite loop over the kafka messages
    for message in consumer:
        js = json.loads(message.value)
        ls = [str(js[key]) for key in fields]

        try:
            cur.execute(f'INSERT INTO public."ErrorReports" ({",".join(fields)}) VALUES({("%s, " * len(ls))[:-2]})', ls)
        except:
            print('Query to insert in the database failed. This is the message received')
            print(message)

        # Save the insert (or any change) to the database
        con.commit()

if __name__ == '__main__':
    cli()
