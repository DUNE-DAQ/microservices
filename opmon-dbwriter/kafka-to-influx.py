#
# @file kafka-to-influx.py Writing opmon info to influx database
# This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

from kafka import KafkaConsumer
from influxdb import InfluxDBClient
import influxdb
import json
import click

import requests
import time
from calendar import timegm

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--kafka-address', type=click.STRING, default="monkafka.cern.ch", help="address of the kafka broker")
@click.option('--kafka-port', type=click.INT, default=30092, help='port of the kafka broker')       
@click.option('--kafka-topics', multiple=True, default=['opmon'], help='topics of the kafka broker')
@click.option('--kafka-consumer-id', type=click.STRING, default='microservice', help='id of the kafka consumer, not really important')
@click.option('--kafka-consumer-group', type=click.STRING, default='opmon_microservice', help='group ID of the kafka consumer, very important to be unique or information will not be duplicated')
@click.option('--influxdb-address', type=click.STRING, default='opmondb.cern.ch', help='address of the influx db')
@click.option('--influxdb-port', type=click.INT, default=31002, help='port of the influxdb')
@click.option('--influxdb-name', type=click.STRING, default='influxv3', help='name used in the influxdb query')
@click.option('--influxdb-create', type=click.BOOL, default=True, help='Creates the influxdb if it does not exists')


def cli(kafka_address, kafka_port, kafka_topics, kafka_consumer_id, kafka_consumer_group, influxdb_address, influxdb_port, influxdb_name, influxdb_create):

    bootstrap = f"{kafka_address}:{kafka_port}"
    print("From Kafka server:",bootstrap)
    
    consumer = KafkaConsumer(bootstrap_servers=bootstrap,
                             group_id=kafka_consumer_group, 
                             client_id=kafka_consumer_id)

    print("Consuming topics:", kafka_topics)
    consumer.subscribe(kafka_topics)
    
    influx = InfluxDBClient(host=influxdb_address, port=influxdb_port)
    db_list = influx.get_list_database()
    print("Available DBs:",db_list)
    if {"name":influxdb_name}  not in db_list:
        print(influxdb_name, "DB not available")
        if influxdb_create:
            influx.create_database(influxdb_name);
            print("New list of DBs:", influx.get_list_database())

    influx.switch_database(influxdb_name)

    # Infinite loop over the kafka messages
    for message in consumer:
        js = json.loads(message.value)

#        print(js)

        ## influxdb implementation
        try:
            influx.write_points([js])
        except influxdb.exceptions.InfluxDBClientError as e:
            print(e)
        except:
            print("Something went wrong: json not sent", js)

        
if __name__ == '__main__':
    cli(show_default=True, standalone_mode=True)
    
