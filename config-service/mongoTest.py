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

import sys
import json
from datetime import datetime
from pymongo import MongoClient

# import orabackend as ora
import sqlqueries

client = MongoClient('localhost', 27017)
db = client['daqling']
coll_dev_configs = db['devel']

locTime = db.command("serverStatus")["localTime"]
timestamp = (locTime - datetime(1970, 1, 1)).total_seconds()
print(locTime)
print(timestamp)

with open(sys.argv[1]) as f:
  config_str = json.load(f)

config_json = {}

config_json['insertionTime'] = locTime
config_json['name'] = sys.argv[2]
config_json['label'] = "NONE"
config_json['configuration'] = config_str

coll_dev_configs.insert_one(config_json)

client.close()

exit(0)

# # BACKUP TO ORA
# res = []

# connection = ora.db_pool.acquire()
# cursor = connection.cursor()
# cursor.execute(queries.insertConfig, [1, "test1", timestamp, timestamp, "NONE", str(config_json)])
# cursor.execute(queries.insertConfig, [2, "test2", timestamp, timestamp, "NONE", str(config_json)])
# cursor.execute(queries.insertConfig, [3, "asd", timestamp, timestamp, "NONE", str(config_json)])
# connection.commit()

# res = []
# ora.perform_query(queries.retrieveExactConfig, {'cName':"asd"}, res)
# print(str(res[0][0][0]))

# print("#####################")

# res2 = []
# ora.perform_query(queries.retrieveConfigsLike, {'cName':"%test%"}, res2)
# print(res2[0][0][0])

# client.close()

