#
# @file kafka-to-influx.py Writing opmon info to influx database
# This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

from kafka import KafkaConsumer
from influxdb import InfluxDBClient
import json
import click


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--kafka-address', type=click.STRING, default="monkafka.cern.ch", help="address of the kafka broker")
@click.option('--kafka-port', type=click.INT, default=30092, help='port of the kafka broker')       
@click.option('--kafka-topics', multiple=True, default=['opmon'], help='topics of the kafka broker')
@click.option('--kafka-consumer-id', type=click.STRING, default='microservice', help='id of the kafka consumer, not really important')
@click.option('--kafka-consumer-group', type=click.STRING, default='opmon_microservice', help='group ID of the kafka consumer, very important to be unique or information will not be duplicated')
@click.option('--influxdb-address', type=click.STRING, default='opmondb.cern.ch', help='address of the influx db')
@click.option('--influxdb-port', type=click.INT, default=31002, help='port of the influxdb')
#@click.option('--influxdb-path', type=click.STRING, default='write', help='path used in the influxdb query')
@click.option('--influxdb-name', type=click.STRING, default='influxdb', help='name used in the influxdb query')

def cli(kafka_address, kafka_port, kafka_topics, kafka_consumer_id, kafka_consumer_group, influxdb_address, influxdb_port, influxdb_name):

    bootstrap = f"{kafka_address}:{kafka_port}"
    print("From Kafka server:",bootstrap)
    
    consumer = KafkaConsumer(bootstrap_servers=bootstrap,
                             group_id=kafka_consumer_group, 
                             client_id=kafka_consumer_id)

    print("Consuming topics:", kafka_topics)
    consumer.subscribe(kafka_topics)

    influx = InfluxDBClient(host=influxdb_address, port=influxdb_port, database=influxdb_name)

#    users = influx.get_list_users()
#    print(users)
    # Infinite loop over the kafka messages
    for message in consumer:
        js = json.loads(message.value)

        print(js)

#        try:
        #influx.write_points([js])
#        except:
#            print("Something went wrong: json not sent", js)
        
#        message = json.loads("{}");
#        message["measurement"] = js["type"];
#        message["tags"] = js["__tags"]
#        message["time"] = js["__time"]
#        message["fields"] = js["__data"]

#        print(message)
        
#        query_intro = js["type"] + ",source_id=" + js["source_id"] + ",partition_id=" + js["partition_id"] #

#        data = js["__data"]
#        data_queries = []
#        for entry, value in data.items():
#            data_queries += [f"{entry}={value}"]#

#        data_query = ','.join(data_queries)
#        full_query =  query_intro + ' ' + data_query

#        reply = requests.post( influx_query, data=full_query)
#        print(reply.text)
#        print(query)

#        ls = [str(js[key]) for key in fields]

#        try:
#            cur.execute(f'INSERT INTO public."ErrorReports" ({",".join(fields)}) VALUES({("%s, " * len(ls))[:-2]})', ls)
#        except:
#            print('Query to insert in the database failed. This is the message received')
#            print(message)
#
#        # Save the insert (or any change) to the database
#        con.commit()

if __name__ == '__main__':
    cli(show_default=True, standalone_mode=True)
    
