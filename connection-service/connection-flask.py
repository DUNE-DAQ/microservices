#
# @file connection-flask.py Simple prototype connection configuration server
# This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import os
import json
import re
from datetime import datetime, timedelta
from collections import namedtuple
from flask import Flask, request, abort


partitions={}
if 'ENTRY_TTL' in os.environ:
  ttl=int(os.environ['ENTRY_TTL'])
else:
  ttl=10
entry_ttl=timedelta(seconds=ttl)
app=Flask(__name__)

@app.route("/")
def dump():
  d=f'<h1>Dump of configuration dictionary</h1>'
  for p in partitions:
    store=partitions[p]
    d=d+f'<h2>Partition {p}</h2> '
    for k,v in store.items():
      d=d+f'<pre>{k}:  {v}</pre>'
  #print(d)
  return d


@app.route("/publish",methods=['POST'])
def publish():
  #  Store multiple connection ids and corresponding uris in a
  #  dictionary associated with the appropriate partition.
  js=json.loads(request.data)
  #print (f"{js=}")
  part=js['partition']
  if part in partitions:
    store=partitions[part]
  else:
    store={}

  timestamp=datetime.now()
  Connection=namedtuple(
    'Connection',['uri','data_type','connection_type','time'])

  for connection in js['connections']:
    #print (f"{connection=}")
    if 'uid' in  connection and 'uri' in connection:
      uid=connection['uid']
      store[uid]=Connection(uri=connection['uri'],
                            connection_type=connection['connection_type'],
                            data_type=connection['data_type'],
                            time=datetime.now())
  partitions[part]=store
  return 'OK'

@app.route("/retract-partition",methods=['POST'])
def retract_partition():
  #print(f"retract_partition() request=[{request.form}]")
  if 'partition' not in request.form:
    abort(400)
  part=request.form['partition']
  if part in partitions:
    partitions.pop(part)
    return 'OK'
  else:
    abort(404)

@app.route("/retract",methods=['POST'])
def retract():
  js=json.loads(request.data)
  good=True
  part=js['partition']
  if part in partitions:
    store=partitions[part]
    for con in js['connections']:
      #print (f"{con=}")
      id=con['connection_id']
      if id in store:
        store.pop(id)
      else:
        print(f"could not find connection_id <{id}>")
        good=False
    if len(store)>0:
      partitions[part]=store
    else:
      # We've deleted the last entry in this partition so delete the
      # partition as well
      partitions.pop(part)

    if good:
      return 'OK'
    else:
      abort(404)
  else:
    abort(404)

@app.route("/getconnection/<part>",methods=['POST','GET'])
def get_connection(part):
  # Find connection uris that correspond to the connection id pattern
  # in the request. The pattern is treated as a regular expression.
  js=json.loads(request.data)
  #print(f"getconnection(): {js=}")
  if part in partitions:
    store=partitions[part]

    if 'uid_regex' in js and 'data_type' in js:
      #print(f"Searching for connections matching uid_regex<{js['uid_regex']}> and data_type {js['data_type']}")
      result=[]
      regex=re.compile(js['uid_regex'])
      dt=js['data_type']
      now=datetime.now()
      # Now try to find all matching entries for this connection
      for uid,con in store.items():
        if regex.search(uid) and con.data_type==dt and now-con.time<entry_ttl:
          #print (f"Found matching entry {uid} {con=}")
          result.append(json.loads('{"uid":'+f'"{uid}",'+
                                   '"uri":'+f'"{con.uri}",'+
                                   '"connection_type":'+f'{con.connection_type},'+
                                   '"data_type":'+f'"{con.data_type}"'+'}'))
      #print(f'result=<{json.dumps(result)}')
      return json.dumps(result)
    else:
      abort(400)
  else:
    print(f"Partition {part} not found")
    abort(404)

