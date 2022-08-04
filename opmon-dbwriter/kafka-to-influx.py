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
import logging

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--kafka-address', type=click.STRING, default="monkafka.cern.ch", help="address of the kafka broker")
@click.option('--kafka-port', type=click.INT, default=30092, help='port of the kafka broker')       
@click.option('--kafka-topics', multiple=True, default=['opmon'], help='topics of the kafka broker')
@click.option('--kafka-consumer-id', type=click.STRING, default='microservice', help='id of the kafka consumer, not really important')
@click.option('--kafka-consumer-group', type=click.STRING, default='opmon_microservice', help='group ID of the kafka consumer, very important to be unique or information will not be duplicated')
@click.option('--kafka-timeout', type=click.INT, default=1000, help='batch sizes in ms to send data to influx')       
@click.option('--batch_size', type=click.INT, default=1000, help='batch sizes to send data to influx')       

@click.option('--influxdb-address', type=click.STRING, default='opmondb.cern.ch', help='address of the influx db')
@click.option('--influxdb-port', type=click.INT, default=31002, help='port of the influxdb')
@click.option('--influxdb-name', type=click.STRING, default='influxv3', help='name used in the influxdb query')
@click.option('--influxdb-create', type=click.BOOL, default=True, help='Creates the influxdb if it does not exists')


def cli(kafka_address, kafka_port, kafka_topics, kafka_consumer_id, kafka_consumer_group, kafka_timeout, batch_size, influxdb_address, influxdb_port, influxdb_name, influxdb_create):

    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S')
    
    bootstrap = f"{kafka_address}:{kafka_port}"
    logging.info("From Kafka server:",bootstrap)
    
    consumer = KafkaConsumer(bootstrap_servers=bootstrap,
                             group_id=kafka_consumer_group, 
                             client_id=kafka_consumer_id,
                             consumer_timeout_ms=kafka_timeout)

    logging.info("Consuming topics:", kafka_topics)
    consumer.subscribe(kafka_topics)
    
    influx = InfluxDBClient(host=influxdb_address, port=influxdb_port)
    db_list = influx.get_list_database()
    logging.info("Available DBs:",db_list)
    if {"name":influxdb_name}  not in db_list:
        print(influxdb_name, "DB not available")
        if influxdb_create:
            influx.create_database(influxdb_name);
            logging.info("New list of DBs:", influx.get_list_database())

    influx.switch_database(influxdb_name)

    while True :
    # Infinite loop over the kafka messages
        batch=[]
        timestamp=0
        try:
            message_it = iter(consumer)
            message = next(message_it)
#            print(message)
            js = json.loads(message.value)
            batch.append(js)
            timestamp=message.timestamp
#            print(js)
#            print(timestamp)
            
        except :
            logging.info("Nothing found")
        
        for message in consumer:
            js = json.loads(message.value)
            batch.append(js)
            if ( message.timestamp != timestamp ) :
                break
            
            
        if  len(batch) > 0 :
            logging.info("Sending", len(batch), "points")
            ## influxdb implementation
            try:
                influx.write_points(batch)
            except influxdb.exceptions.InfluxDBClientError as e:
                logging.error(e)
            except:
                logging.error("Something went wrong: json batch not sent")

        

#        else :
#            print("Nothing is received")
        
            
if __name__ == '__main__':
    cli(show_default=True, standalone_mode=True)
    
