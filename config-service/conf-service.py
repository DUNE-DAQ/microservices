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
import json, re
import threading
import time, logging
import signal, os
from datetime import datetime
from pymongo import MongoClient
import configconfig as config

import flask
from flask import Flask, Response, request, render_template, abort
from flask_restful import Api, Resource, reqparse
from flask_caching import Cache
from apispec import APISpec
from bson.json_util import loads, dumps
__version__='1.0.1'

'''
Preliminary setup
'''

# Configuration
active = True

# Logger
log = logging.getLogger('service_logger')
log.setLevel(logging.DEBUG)
fh = logging.FileHandler(config.logfile)
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
log.addHandler(fh)
log.addHandler(ch)

def resource_not_found(e):
    return flask.jsonify(error=str(e)), 404

'''
Resources
'''
class BaseResource(Resource):
  def get(self):
    try:
        self.real_get()
    except Exception as exception:
        # Will catch all errors in your subclass my_get method
        log.error("exception caught")
        log.error(request.url)
        log.error(type(exception).__name__)
        log.error(self.log_data())

        # Re-raise if you want (or not)
        raise exception

  def base_get(self): # virtual-like
    raise NotImplementedError()

  def log_data(self): # virtual-like
    raise NotImplementedError()

'''
Most typical MongoDB query
'''
def getDocs(filter, coll, projection=None):
  log.debug(f'Will run Mongo search: {filter}')
  docs = coll.find(filter, projection)
  log.debug(f'Retrieved document count: {docs.count()}')
  confs = {}
  for d in docs:
    confs[d['name']] = str(dumps(d))
  return confs

def getCollections():
  docs = mongo_db.list_collection_names()
  log.debug(docs)
  return docs

def extract_data(request, dico, conf_name):
  app_name = request.args.get('app_name')
  cmd_name = request.args.get('cmd_name')
  print(app_name)
  print(cmd_name)

  if app_name:
    app_data = dico.get(app_name)
    if not app_data:
      abort(404, description=f"{app_name} app not found in configuration {conf_name}")
    dico = app_data

    if cmd_name:
      cmd_data = dico.get(cmd_name)
      if not cmd_data:
        abort(404, description=f"{cmd_name} app not found in configuration {conf_name}, application {app_name}")
      dico = cmd_data

  if cmd_name and not app_name:
    print(cmd_name)
    cmd_data = dico.get(cmd_name)
    print(cmd_data)
    if not cmd_data:
      abort(404, description=f"{cmd_name} cmd not found in configuration {conf_name} (did you forget to provide the app_name?)")
    dico = cmd_data

  res = flask.make_response(flask.jsonify(dico))

  if res.data == b'{}\n':
    res.status_code = 204
  return res


'''
Resources for Flask app
'''
class RetrieveLast(BaseResource):
  def get(self):
    log.debug(f'GET request with args: {request.args}')
    conf_name = request.args.get('name')

    if conf_name:
      log.debug(f"Looking for config {request.args['name']}")
      dico = {}
      try:
        documents = mongo_db[conf_name].find().sort("version", -1)
        dico = json.loads(dumps(documents[0]))
      except:
        abort(404, description=f'Couldn\'t find the configuration {conf_name}')
      return extract_data(request, dico, conf_name)

    else:
      abort(404, description=f"You need to provide a configuration name at least")


class RetrieveVersion(BaseResource):
  def get(self):
    log.debug(f'GET request with args: {request.args}')
    conf_name = request.args["name"]
    version = request.args["version"]

    if conf_name and version:
      log.debug(f"Looking for version {version} of config {conf_name}")
      dico = {}
      try:
        document = mongo_db[conf_name].find_one({'version': int(version)})
        dico = json.loads(dumps(document))
      except:
        abort(404, description=f'Couldn\'t find the version {version} of the configuration {conf_name}')
      return extract_data(request,  dico, conf_name)

    else:
      abort(404, description=f"You need to provide a configuration name and version")

class Create(BaseResource):
  def get(self):
    log.debug(f'GET request with args: {request.args}')
    return app.send_static_file('conf-form.html')

  def post(self):
    log.debug(f'POST request with args: {request.args}')
    coll_name = request.args['collection']

    version = 0
    try:
      documents = mongo_db[coll_name].find().sort("version", -1)
      version = documents[0]["version"] + 1
      log.debug(f'Version bumped to {version}')
    except:
      log.debug(f"No collection exist with name '{coll_name}'")
    # conf_req = request.json
    res = {}
    db_time = mongo_db.command("serverStatus")["localTime"]
    conf_json = request.json
    conf_json['insertionTime'] = db_time
    conf_json['version'] = version
    try:
      ins_res = mongo_db[coll_name].insert_one(conf_json)
      res['success'] = True
      res['acknowledged'] = ins_res.acknowledged
      res['docid'] = str(ins_res.inserted_id)
      res['msg'] = "Uploaded successfully collection \'" + coll_name + "\' version " + str(version)
      res['coll_name'] = coll_name
      res['version'] = version
    except Exception as e:
      res['error'] = str(e)
      res['success'] = False
    return flask.make_response(flask.jsonify(res))



class Update(BaseResource):
  def get(self):
    return 'Not implemented yet, due to ONLY-APPEND policy.'
  def put(self):
    return 'Not implemented yet, due to ONLY-APPEND policy.'

class ListConfigs(BaseResource):
  def get(self):
    log.debug(f'GET request with args: {request.args}')
    res = getCollections()
    configs = {'configs': []}
    for k in res:
      configs['configs'].append(k)
    return flask.make_response( flask.jsonify( configs ))

class ListVersions(BaseResource):
  def get(self):
    log.debug(f'GET request with args: {request.args}')
    name=request.args['name']

    configs = {
      'config': name,
      'versions': []
    }
    if request.args['name']:
      log.debug(f"Looking for versions for name '{name}'")
      documents = mongo_db[name].find()
      for k in documents:
        configs['versions'].append(k['version'])

    return flask.make_response( flask.jsonify( configs ))

'''
Mongo connection
'''
mongo_client = None
mongo_db = None
coll_configs = None
if config.mongo_pass != '':
  mongo_connection_string = f'mongodb://{config.mongo_user}:{config.mongo_pass}@{config.mongo_host}:{config.mongo_port}'
elif config.mongo_user != '':
  mongo_connection_string = f'mongodb://{config.mongo_user}@{config.mongo_host}:{config.mongo_port}'
else:
  mongo_connection_string = f'mongodb://{config.mongo_host}:{config.mongo_port}'

try:
  mongo_client = MongoClient(mongo_connection_string)
  mongo_db = mongo_client[config.mongo_db]
except:
  log.error('Please check your configuration details for the MongoDB connection!')
  log.error(f'base connection_string=mongodb://{config.mongo_host}:{config.mongo_port}/{config.mongo_db}')
  log.error(f'connection_username="{config.mongo_user}"')
  if config.mongo_pass != '':
    log.error('connection_password is defined')
  else:
    log.error('connection_password is NOT defined')
  exit(1)

'''
Main flask app
'''
app = Flask(__name__, static_url_path='',
            static_folder='web/static',
            template_folder='web/templates')
app.errorhandler(404)(resource_not_found)

# app.config['CACHE_TYPE'] = 'redis' # easier to scale it and async disk writes provides DB dumps.

cache = Cache(app)
api = Api(app)
api.add_resource(RetrieveLast, "/retrieveLast", methods=['GET'])
api.add_resource(RetrieveVersion, "/retrieveVersion", methods=['GET'])
api.add_resource(Create, "/create", methods=['GET', 'POST'])
api.add_resource(Update, "/update", methods=['GET', 'PUT'])
api.add_resource(ListConfigs, "/listConfigs", methods=['GET'])
api.add_resource(ListVersions, "/listVersions", methods=['GET'])

@app.route('/')
def index():
  return f'DAQling Configuration Management Service v{__version__}'

'''
Normally this app is spawned by Gunicorn
'''
#if __name__ == '__main__':
#  app.run(debug=config['debug'])

'''
As a testserver run this instead:
'''
# app.run(host=config.service_host, port=config.service_port, debug=True)
# app.run(host="localhost", port=11111, debug=True)
