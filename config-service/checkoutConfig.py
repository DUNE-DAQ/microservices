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
import requests
from pathlib import Path
from os import environ as env

parser = argparse.ArgumentParser(description='Tool for retrieve and dump from configuration database')
parser.add_argument('name', metavar='name', type=str, 
                    help='JSON configuration name to retrieve. Use \"list\" to print the list of available configuration sets.')
parser.add_argument('version', metavar='version', type=int, nargs='?',default=None,
                    help="Version of the configuration")
args = parser.parse_args()

configs_dir=env['DAQ_CONFIG_DIR']
service_configs_file=env['DAQ_SCRIPT_DIR']+'Configuration/config/service-config.json'

with open(service_configs_file) as config_file:
  config = json.load(config_file)

port = config['service_port']
host = config['service_host']

if args.name == "list":
  r = requests.get('http://'+host+':'+str(port)+'/listConfigs')
  print('List of available configurations below:')
  print(r.json()['configs'])
  exit()

try:
  if args.version is None:
    r = requests.get('http://'+host+':'+str(port)+'/retrieveLast?name='+args.name)
  else:
    r = requests.get('http://'+host+':'+str(port)+'/retrieveVersion?name='+args.name+'&version='+str(args.version))
except requests.exceptions.RequestException as e:  # This is the correct syntax
  print("Request failed, check that service is running.")
  print("Error message:")
  raise SystemExit(e)
if(r.status_code==200):
  
  response_json = json.loads(r.json())
  deps_dir = env['DAQ_CONFIG_DIR']+args.name
  # base_dir_uri = Path(deps_dir).as_uri() + '/'
  deps_dir = deps_dir + "_v" + str(response_json['version']) +'/'

  Path(deps_dir).mkdir(parents=True, exist_ok=True)

  for f in response_json["files"]:
    # open file with w+
    name = response_json["files"][f]['name']
    file_content = json.loads(response_json["files"][f]['file_content'])
    # if name=="config":
    #   configs_json=response_json["deps"][dep]['file_content']
    with open(deps_dir+name+'.json','w+') as template_file:
      json.dump(file_content, template_file, indent=2)
else:
  print("Unexpected http status code: "+r.status_code)
