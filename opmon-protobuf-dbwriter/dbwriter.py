# @file dbwriter.py Writing Opmon entries into InfluxDB
#  This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import kafkaopmon.OpMonSubscriber as opmon_sub
import google.protobuf.json_format as pb_json
from google.protobuf.timestamp_pb2 import Timestamp
import opmonlib.opmon_entry_pb2 as opmon_schema

from influxdb import InfluxDBClient
from functools import partial
import json
import click
import logging
import queue
import threading


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
# subscriber options
@click.option('--subscriber-bootstrap', type=click.STRING, default="monkafka.cern.ch:30092", help="boostrap server and port of the OpMonSubscriber")
@click.option('--subscriber-group',     type=click.STRING, default=None, help='group ID of the OpMonSubscriber')
@click.option('--subscriber-timeout',   type=click.INT,    default=500, help='timeout in ms used in the OpMonSubscriber')
@click.option('--subscriber-topic',     type=click.STRING, multiple=True, default=['opmon_stream'] )

#influx options
@click.option('--influxdb-address', type=click.STRING, default='opmondb.cern.ch', help='address of the influx db')
@click.option('--influxdb-port', type=click.INT, default=31002, help='port of the influxdb')
@click.option('--influxdb-name', type=click.STRING, default='test_influx', help='name used in the influxdb query')
@click.option('--influxdb-create', type=click.BOOL, default=True, help='Creates the influxdb if it does not exists')

@click.option('--debug',       type=click.BOOL, default=True, help='Set debug print levels')

def cli(subscriber_bootstrap, subscriber_group, subscriber_timeout, subscriber_topic,
        influxdb_address, influxdb_port, influxdb_name, influxdb_create,
        debug):

    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG if debug else logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S')

#    influx = InfluxDBClient(host=influxdb_address, port=influxdb_port)
#    db_list = influx.get_list_database()
#    logging.info("Available DBs:",db_list)
#    if {"name":influxdb_name}  not in db_list:
#        logging.warning(influxdb_name, "DB not available")
#        if influxdb_create:
#            influx.create_database(influxdb_name);
#            logging.info("New list of DBs:", influx.get_list_database())

#    influx.switch_database(influxdb_name)

    sub = opmon_sub.OpMonSubscriber( bootstrap=subscriber_bootstrap,
                                     topics=subscriber_topic,
                                     group_id = subscriber_group,
                                     timeout_ms = subscriber_timeout)

    # this is a list of single json entries
    q = queue.Queue()

    callback_function = partial(process_entry, 
                                q = q )
    
    sub.add_callback(name="to_influx", 
                     function=callback_function)
    
    sub.start()

def process_entry( entry : opmon_schema.OpMonEntry, 
                   q : queue.Queue ) :
    d = to_dict(entry)
    js = json.dumps(d)
    logging.debug(js)
    #q.put(js)


def to_dict( entry : opmon_schema.OpMonEntry ) -> dict :
    ret = dict(measurement = entry.measurement)
    ret['fields'] = unpack_payload(entry)
    ret['tags'] = create_tags(entry)
    ret['time'] = entry.time.ToJsonString()
    return ret

def unpack_payload( entry : opmon_schema.OpMonEntry ) -> dict :
    data = entry.data
    ret = dict()
    for key in data :
        value = data[key]
        casted_value = getattr(value, value.WhichOneof('kind'))
        ret[key] = casted_value
               
    return ret


def create_tags( entry : opmon_schema.OpMonEntry ) -> dict :
    opmon_id = entry.origin
    #session and application
    tags = dict(session = opmon_id.session, 
                application = opmon_id.application)
    
    #element and subelements
    struct = opmon_id.substructure
    for i in range(len(struct)) :
        name='sub'*i + 'element'
        tags[name] = struct[i]

    #custom origin
    tags |= entry.custom_origin

    return tags

if __name__ == '__main__':
    cli()

