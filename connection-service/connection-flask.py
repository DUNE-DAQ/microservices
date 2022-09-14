#
# @file connection-flask.py Simple prototype connection configuration server
# This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import os
import json

from flask import Flask, request, abort

class configmgr(object):
  def __init__(self, name):
    self.name=name

    if name != "":
      self.store={}
      if "namespace" in os.environ:
        self.namespace=os.environ["namespace"]
      else:
        self.namespace="default"

        from kubernetes import client, config
        config.load_config()
        self.core_api = client.CoreV1Api()
        try:
          body=self.core_api.read_namespaced_config_map(name,self.namespace)
        except Exception as ex:
          print (f"Creating configMap {name}")
          body=client.V1ConfigMap(api_version="v1",
                                  metadata={"name":name},
                                  data={"app":""}
                                  )
          self.core_api.create_namespaced_config_map(self.namespace,body)
        for item in body.data:
          if body.data[item]!='{}':
            self.store[item]=body.data[item]
      print(self.store)

  def update(self, newdict):
    if self.name != "":
      body=self.core_api.read_namespaced_config_map(self.name,self.namespace)
      for item in newdict:
        body.data[item]=json.dumps(newdict[item])
      self.core_api.patch_namespaced_config_map(self.name,self.namespace,body)
  def delete(self, item):
    if self.name != "":
      body=self.core_api.read_namespaced_config_map(self.name,self.namespace)
      if item in body.data:
        body.data[item]='{}'
        #print(f"body.data=<{body.data}>")
      self.core_api.patch_namespaced_config_map(self.name,self.namespace,body)

partitions={}
#store={'app':{},'source':{},'sourceconn':{},'connection':{}}
if "configMap" in os.environ:
  cmgr=configmgr(os.environ["configMap"])
  for item in cmgr.store:
    partitions[item]={}
    if cmgr.store[item]!="":
      pdict=json.loads(cmgr.store[item])
      for a in pdict:
        partitions[item][a]=pdict[a]
else:
  cmgr=configmgr("")
app=Flask(__name__)

@app.route("/")
def dump():
  d=f'<h1>Dump of configuration dictionary</h1>'
  for p in partitions:
    store=partitions[p]
    d=d+f'<h2>Partition {p}</h2> '
    for n in store:
      d=d+f'<h3>{n}</h3> <pre>{store[n]}</pre>'
  print(d)
  return d

@app.route("/publish",methods=['POST'])
def publish():
  #  Store uri associated with an endpoint. If a connection is given,
  # use the bind_endpoint and uri of the connection otherwise expect
  # the endpint and uri to be given as part of the form

  #print(f"publish() request=[{request.form}]")
  part=request.form['partition']
  if part in partitions:
    store=partitions[part]
  else:
    store={'endpoint': {}, 'connection':{}, 'connection_type':{}}

  if 'endpoint' in request.form:
    ep=json.loads(request.form['endpoint'])
    ep=json.dumps(ep)
    store['endpoint'][ep]=request.form['uri']
    if 'connection_type' in request.form:
      store['connection_type'][ep]=request.form['connection_type']
  if 'connection' in request.form:
    conn=json.loads(request.form['connection'])
    ep=json.dumps(conn['bind_endpoint'])
    store['endpoint'][ep]=conn['uri']
    store['connection'][ep]=conn

  partitions[part]=store
  cmgr.update(partitions)
  return 'OK'

@app.route("/retract-partition",methods=['POST'])
def retract_partition():
  #print(f"retract_partition() request=[{request.form}]")
  part=request.form['partition']
  if part in partitions:
    partitions.pop(part)
    cmgr.delete(part)
    return 'OK'
  else:
    abort(404)

@app.route("/retract",methods=['POST'])
def retract():
  print(f"retract() request=[{request.form}]")
  part=request.form['partition']
  if part in partitions:
    store=partitions[part]
    if 'endpoint' in request.form:
      endpoint=json.loads(request.form['endpoint'])
      endpoint=json.dumps(endpoint)
      print(f"retracting endpoint <{endpoint}>")
      if endpoint in store['endpoint']:
        store['endpoint'].pop(endpoint)
        partitions[part]=store
        cmgr.update(partitions)
        return 'OK'
      else:
        print(f"could not find endpoint <{endpoint}>")
        abort(404)
    elif 'connection' in request.form:
      conn=json.loads(request.form['connection'])
      ep=json.dumps(conn['bind_endpoint'])
      if ep in store['connection']:
        store['connection'].pop(ep)
        store['endpoint'].pop(ep)
        partitions[part]=store
        cmgr.update(partitions)
        return 'OK'
      else:
        abort(404)
  else:
    abort(404)

@app.route("/getendpoint/<part>",methods=['POST','GET'])
def get_endpoint(part):
  if part in partitions:
    store=partitions[part]

    endpoint=json.loads(request.form['endpoint'])
    matches=[]
    ctype=""
    for entry in store['endpoint']:
      match=True
      ep=json.loads(entry)
      for item in endpoint:
        #print(f"item=<{item}> entry=<{ep[item]}> search=<{endpoint[item]}>")
        if ep[item]!=endpoint[item] and endpoint[item] != '*':
          match=False
      if match:
        matches.append(store['endpoint'][entry])
        if entry in store['connection']:
          conn=store['connection'][entry]
          ctype=conn['connection_type']
        if entry in store['connection_type']:
          ctype=store['connection_type'][entry]
    if len(matches)>0:
      result='{'+f'"uris":['
      for n in range(len(matches)):
        result=result+'"'+matches[n]+'"'
        if n<len(matches)-1:
          result=result+','
      result=result+'],'+f'"connection_type":"{ctype}"'+'}'
      #print(f"result = <{result}>")
      dummy=json.loads(result)
      print(f"json   = <{result}>")
      return(result)
    else:
      abort(404)
  else:
    #print(f"Partition {part} not found")
    abort(404)

def lookup(part, map, key):
  if part in partitions:
    store=partitions[part]
    #print(f"Looking for <{key}> in <{store[map]}>")
    if key in store[map]:
      val=store[map][key]
      #print(f"lookup key={key} {map}[key]={val}")
      return(val)
    else:
      abort(404)
  else:
    abort(404)

@app.route("/getconnection/<part>",methods=['POST','GET'])
def get_connection(part):
  # Get the connection associated with an endpoint
  ep=json.loads(request.form['endpoint'])
  print(f"ep=<{ep}")
  return lookup(part,'connection',json.dumps(ep))

