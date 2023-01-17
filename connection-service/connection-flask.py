#
# @file connection-flask.py Simple prototype connection configuration server
# This is part of the DUNE DAQ software, copyright 2020.
#  Licensing/copyright details are in the COPYING file that you should have
#  received with this code.
#

import os
import json
import re
from threading import Lock
from io import StringIO
from datetime import datetime, timedelta
from collections import namedtuple
from flask import Flask, request, abort


partitions={}
partlock=Lock()

if 'ENTRY_TTL' in os.environ:
  ttl=int(os.environ['ENTRY_TTL'])
else:
  ttl=10
entry_ttl=timedelta(seconds=ttl)

last_stats=datetime.now()
npublishes=0
nlookups=0
lookup_time=timedelta(0)
publish_time=timedelta()
maxpartitions=0
maxentries={}

app=Flask(__name__)

@app.route("/")
def dump():
  now=datetime.now()
  dstream=StringIO()
  dstream.write(f'<h1>Dump of configuration dictionary</h1>')
  dstream.write(f"<h2>Active partitions</h2><p>")
  if len(partitions)>0:
    pad=' style="padding-left: 1em;padding-right: 1em"'
    dstream.write(f'<table style="border: 1px solid black">'
                  f'<tr style="background: #e0e0e0"><th{pad}>Partition</th>'
                  f'<th{pad}>Entries</th></tr>')
    for p in partitions:
      dstream.write(f'<tr><td{pad}>{p}'
                    f'</td><td{pad}>{len(partitions[p])}</td></tr>')
    dstream.write(f"</table>")
    for p in partitions:
      store=partitions[p]
      dstream.write(f'<h2>Partition {p}</h2><p>')
      for k,v in store.items():
        if now-v.time<entry_ttl:
          dstream.write(f'{k}: {v}</br>')
        else:
          dstream.write(f'<strike>{k}: {v}</strike></br>')
      dstream.write("</p>")
  else:
    dstream.write(f"None</p>")
  dstream.write(f"<hr><h2>Server statistics</h2>")
  stats_to_html(dstream)
  dstream.seek(0)
  return dstream.read()

def stats_to_html(dstream):
  dstream.write(f"<p>Since {last_stats}</p>")
  if npublishes>0:
    avg_pub=publish_time/npublishes
  else:
    avg_pub=timedelta()
  dstream.write(f"<p>{npublishes} calls to publish in total time {publish_time} "
                f"(average {avg_pub.microseconds} &micro;s per call)</p>")
  if nlookups>0:
    avg_lookup=lookup_time/nlookups
  else:
    avg_lookup=timedelta()
  dstream.write(f"<p>{nlookups} calls to lookup in total time {lookup_time} "
                f"(average {avg_lookup.microseconds} &micro;s per call)</p>")
  dstream.write(f"<p>Maximum number of partitions active = {maxpartitions}</p>")
  for part in maxentries:
    dstream.write(f"<p>Maximum entries in partition {part} = {maxentries[part]}</p>")

@app.route("/stats")
def dumpStats():
  dstream=StringIO()
  dstream.write(f'<h1>Connection server statistics</h1>')
  stats_to_html(dstream)
  dstream.seek(0)
  return dstream.read()

@app.route("/publish",methods=['POST'])
def publish():
  #  Store multiple connection ids and corresponding uris in a
  #  dictionary associated with the appropriate partition.
  timestamp=datetime.now()
  js=json.loads(request.data)
  #print (f"{js=}")
  part=js['partition']

  partlock.acquire()
  if part in partitions:
    store=partitions[part]
  else:
    store={}
    partitions[part]=store
    global maxpartitions
    if len(partitions)>maxpartitions:
      maxpartitions=len(partitions)
    if not part in maxentries:
      #print(f"Setting maxentries[{part}] to 0")
      maxentries[part]=0

  Connection=namedtuple(
    'Connection',['uri','data_type','connection_type','time'])

  for connection in js['connections']:
    #print (f"{connection=}")
    if 'uid' in  connection and 'uri' in connection:
      uid=connection['uid']
      store[uid]=Connection(uri=connection['uri'],
                            connection_type=connection['connection_type'],
                            data_type=connection['data_type'],
                            time=timestamp)
  elapsed=datetime.now()-timestamp
  #print(f"publish took {elapsed.microseconds} us to add {len(js['connections'])} connections")
  global npublishes, publish_time
  publish_time+=elapsed
  npublishes+=1
  if len(store)>maxentries[part]:
    maxentries[part]=len(store)

  partlock.release()
  return 'OK'

@app.route("/retract-partition",methods=['POST'])
def retract_partition():
  #print(f"retract_partition() request=[{request.form}]")
  if 'partition' not in request.form:
    abort(400)
  part=request.form['partition']
  partlock.acquire()
  if part in partitions:
    partitions.pop(part)
    partlock.release()
    return 'OK'
  else:
    partlock.release()
    abort(404)

@app.route("/retract",methods=['POST'])
def retract():
  js=json.loads(request.data)
  good=True
  part=js['partition']
  partlock.acquire()
  if part in partitions:
    store=partitions[part]
    for con in js['connections']:
      #print (f"{con=}")
      id=con['connection_id']
      if id in store:
        store.pop(id)
      else:
        print(f"retract() could not find connection_id <{id}>")
        good=False
    if len(store)==0:
      # We've deleted the last entry in this partition so delete the
      # partition as well
      partitions.pop(part)
  else:
    good=False
  partlock.release()
  if good:
    return 'OK'
  else:
    abort(404)

@app.route("/getconnection/<part>",methods=['POST','GET'])
def get_connection(part):
  # Find connection uris that correspond to the connection id pattern
  # in the request. The pattern is treated as a regular expression.
  now=datetime.now()
  js=json.loads(request.data)

  if 'uid_regex' in js and 'data_type' in js:
    #print(f"Searching for connections matching uid_regex<{js['uid_regex']}> and data_type {js['data_type']}")
    result=[]
    regex=re.compile(js['uid_regex'])
    dt=js['data_type']
    partlock.acquire()
    if part in partitions:
      store=partitions[part]
      matched=[]
      for uid,con in store.items():
        if regex.search(uid) and con.data_type==dt and now-con.time<entry_ttl:
          #print (f"Found matching entry {uid} {con=}")
          #result.append('{'
          #              f'"uid":"{uid}",'
          #              f'"uri":"{con.uri}",'
          #              f'"connection_type":{con.connection_type},'
          #              f'"data_type":"{con.data_type}"'
          #              '}')
          matched.append((uid,con))
      partlock.release()
      # We should now be able to construct JSON string while other threads
      # have access to the partition dict
      for uid,con in matched:
        result.append('{'
                      f'"uid":"{uid}",'
                      f'"uri":"{con.uri}",'
                      f'"connection_type":{con.connection_type},'
                      f'"data_type":"{con.data_type}"'
                      '}')
      td=datetime.now()-now
      #print(f"Lookup took {td.microseconds} us to find {len(result)} connections")
      global nlookups, lookup_time
      # Should we have the lock while updating statistics? It doesn't
      # really matter if the stats aren't entirely accurate.
      nlookups+=1
      lookup_time+=td
      return "["+",".join(result)+"]"
    else:
      partlock.release()
      print(f"get_connection() Partition {part} not found")
      abort(404)
  else:
    abort(400)

