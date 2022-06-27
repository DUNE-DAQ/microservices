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
@click.option('--kafka-consumer-id', type=click.STRING, default='microservice',
              help='id of the kafka consumer, not really important')
@click.option('--kafka-consumer-group', type=click.STRING, default='opmon_microservice',
              help='group ID of the kafka consumer, very important to be unique or information will not be duplicated')
@click.option('--influxdb-address', type=click.STRING, default='opmondb.cern.ch',
              help='address of the influx db')
@click.option('--influxdb-port', type=click.INT, default=31002,
              help='port of the influxdb')
@click.option('--influxdb-path', type=click.STRING, default='write',
              help='path used in the influxdb query')
@click.option('--influxdb-name', type=click.STRING, default='influxdb',
              help='name used in the influxdb query')

def cli(kakfa_broker, karkfa_port, kafka_topics, kafka_client_id, kafka_group_id, 
        influx_address, influx_port, influx_path, influx_name):

    consumer = KafkaConsumer(kafka_topics,
                            bootstrap_servers=kakfa_broker,
                            group_id=kafka_group_id, 
                            client_id=kafka_client_id)

    # Infinite loop over the kafka messages
    for message in consumer:
        js = json.loads(message.value)
        print js

        ls = [str(js[key]) for key in fields]

#        try:
#            cur.execute(f'INSERT INTO public."ErrorReports" ({",".join(fields)}) VALUES({("%s, " * len(ls))[:-2]})', ls)
#        except:
#            print('Query to insert in the database failed. This is the message received')
#            print(message)
#
#        # Save the insert (or any change) to the database
#        con.commit()

if __name__ == '__main__':
    cli()
