"""
 Copyright (C) 2019-2021 CERN
 
 DAQling is free software: you can redistribute it and/or modify
 it under the terms of the GNU Lesser General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 
 DAQling is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU Lesser General Public License for more details.
 
 You should have received a copy of the GNU Lesser General Public License
 along with DAQling. If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import json
import threading
import time, logging
import signal, os, sys
import cx_Oracle
from datetime import datetime
from pymongo import MongoClient

import orabackend as ora
import sqlqueries

# Arg parse
parser = argparse.ArgumentParser(description='MongoDB to Oracle async archiver for DAQling configurations.')
parser.add_argument('--config', metavar='CONFIG', type=str, nargs=1, 
                    default='config/archiver-config.json', 
                    help='JSON configuration file for archiver.')
args = parser.parse_args()

# Configuration
active = True
try:
  with open(args.config) as config_file:
    config = json.load(config_file)
except:
  print('Failed to process configuration file: ', sys.exc_info()[0])
  exit(1)

# Logger
log = logging.getLogger('archiver_logger')
fh = logging.FileHandler(config['logfile'])
ch = logging.StreamHandler()
loglevel = None
if not config['loglevel']:
  loglevel = logging.INFO
elif config['loglevel'] == 'DEBUG':
  loglevel = logging.DEBUG
elif config['loglevel'] == 'INFO':
  loglevel = logging.INFO
log.setLevel(loglevel)
fh.setLevel(loglevel)
ch.setLevel(loglevel)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
log.addHandler(fh)
log.addHandler(ch)
log.info('Preparing startup...')

# Oracle connection
try:
  ora.init(config)
  sqlq = sqlqueries.SqlQueries()
  sqlq.init(config)
except IOError:
  log.error('Please check your configuration details for the Oracle connection!')
  exit(1)

# Mongo connection
mongo_client = None
mongo_db = None
coll_configs = None
try:
  mongo_client = MongoClient(config['mongo_host'], config['mongo_port'])
  mongo_db = mongo_client[config['mongo_db']]
  coll_configs = mongo_db[config['mongo_coll']]
except:
  log.error('Please check your configuration details for the MongoDB connection!')
  exit(1)

# Poller
log.info('Succesfully connected to databases. Preparing poller.')
def archiveLatest():
  log.info('Poller looks for newer entries than in Oracle.')
  row_res = []
  ora.perform_query(sqlq.getLastInsert, {}, row_res)
  utc_secs = 0.0
  if row_res:
    utc_secs = row_res[0][0][0]
  last_ins_time = datetime.utcfromtimestamp(utc_secs)
  log.debug(str(last_ins_time))
  new_confs = coll_configs.find({ 'insertionTime':{'$gt':last_ins_time} })
  log.info('Retrieved new configuration count: ' + str(new_confs.count()))
  # Archive new configs
  if new_confs.count():
    connection = None
    while not connection:
      try:
        connection = ora.db_pool.acquire()
      except:
        log.error('Faild to get a connection to the Oracle database. Trying again...')
    cursor = connection.cursor()
    for doc in new_confs:
      log.debug(str(doc['_id']))
      conf_utc = (doc['insertionTime'] - datetime(1970,1,1)).total_seconds()
      cursor.execute(sqlq.insertConfig, [str(doc['_id']), doc['name'], conf_utc, conf_utc, doc['label'], str(doc)])
    connection.commit()
    log.info('New configurations committed.')

# SIGQUIT handler
def sighandler(signum, frame):
  global active
  log.info('Sighandler received: ' + str(signum))
  # Setting shouldStop for poller
  if signum == 3 or signum == 6:
    active = False
    log.info('Graceful ABRT or QUIT -> Let main thread to join, then bye!')

# Registering signals
log.info('Main thread sets up sighandler.')
signal.signal(signal.SIGQUIT, sighandler)
signal.signal(signal.SIGABRT, sighandler)

# In every configured minute, archive new configurations
checks = 0
while(active):
  time.sleep(1)
  checks += 1
  if checks == (config['poll_time_mins'] *60):
    archiveLatest()
    checks = 0

# Before exit, close connections.
mongo_client.close()

# Byez
exit(0)

