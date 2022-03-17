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
from os import environ as env
import re
import json
import requests
import argparse

parser = argparse.ArgumentParser(description='Upload tool for configuration database')
parser.add_argument('dir_name', metavar='dir_name', type=str, 
                    help='JSON configuration folder to be stored')
# parser.add_argument('name', metavar='Name', type=str,nargs='?',default='',
#                     help="Name of configuration")
args = parser.parse_args()

configs_dir=env['DAQ_CONFIG_DIR']
service_configs_file=env['DAQ_SCRIPT_DIR']+'Configuration/config/service-config.json'

with open(service_configs_file) as config_file:
  config = json.load(config_file)

port = config['service_port']
host = config['service_host']
#update refs.



data = {}
data["files"]={}
# data["dir_name"]=args.dir_name
i = 0   
deps_dir = configs_dir+args.dir_name+'/'
for filename in os.listdir(deps_dir):
  if filename[-5:]!='.json':
    print('dir:',filename)
    continue
  with open(deps_dir+filename,'r') as file:
    data['files'][i]= {}
    data['files'][i]["name"]=filename[0:-5] 
    data['files'][i]["file_content"] = file.read()
  i+=1

# with open(configs_dir+'testoutput','w+') as file:
#   json.load(data,file)
# print(data)

# strip the version from name
dir_name = args.dir_name
pattern = "_v[0-9]+"
dir_name_mod = re.sub(pattern, '', dir_name)

header = {'Accept' : 'application/json','Content-Type':'application/json'}
# if not args.name:
#   coll_name=args.dir_name
# else:
#   coll_name=args.name
coll_name=dir_name_mod
print('sending request to: '+'http://'+host+':'+str(port)+'/create?collection='+coll_name)
response = requests.post('http://'+host+':'+str(port)+'/create?collection='+coll_name,headers=header,data=json.dumps(data))
print(response.json()['msg'])
