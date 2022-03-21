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

import os
import re
import json
import requests
import argparse
from pathlib import Path
parser = argparse.ArgumentParser(description='Upload tool for configuration database')
parser.add_argument('dir_name',
                    metavar='dir_name',
                    type=str,
                    help='JSON configuration folder to be stored')
parser.add_argument('--service-address',
                    metavar='service-address',
                    type=str,
                    default='np04-srv-010.cern.ch:31011',
                    help='The host address for the config service')
parser.add_argument('--collection-name',
                    type=str,
                    default=None,
                    help='What the collection name should be')
args = parser.parse_args()

def get_json_recursive(path):
  data = {
    'files':[],
    'dirs':[],
  }

  for filename in os.listdir(path):
    if os.path.isdir(path/filename):
      dir_data = {
        'name' : filename,
        'dir_content': get_json_recursive(path/filename)
      }
      data['dirs'].append(dir_data)
      continue

    if not filename[-5:] == ".json":
      print(f'WARNING! Ignoring {path/filename} as this is not a json file!')
      continue

    with open(path/filename,'r') as f:
      file_data = {
        "name": filename[0:-5],
        "configuration": json.load(f)
      }
      data['files'].append(file_data)
  return data

conf_data = get_json_recursive(Path(args.dir_name))

header = {
  'Accept' : 'application/json',
  'Content-Type':'application/json'
}

coll_name = args.collection_name if args.collection_name else os.path.basename(args.dir_name)
print(f'Attempting to add the configuration {coll_name} to the configuration database.')
response = requests.post(
  'http://'+args.service_address+'/create?collection='+coll_name,
  headers=header,
  data=json.dumps(conf_data)
)

print(response.json())
