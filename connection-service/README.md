# Connection-service

 This service provides a very simple flask based
server to serve connection information to DAQ applications.

## Installation

 Build the docker image
```
docker buildx build --tag connection-service:0.0.1 .
```

 Apply the kubernetes manifest from connection-service.yaml. This
 should start a service called connection-flask in the namespace
 connections.

```
kubectl apply -f connection-service.yaml
```

To test the basic operation of the server, you can connect to  pod in the k8s cluster and try getting the root document.

```
> kubectl exec gordon-test -i -t -- bash
[root@gordon-test /]# curl http://connection-flask.connections:5000
<h1>Dump of configuration dictionary</h1>[root@gordon-test /]# 
[root@gordon-test /]#
```

## REST interface

  The server reponds to the following uris

### /publish
 Allows publication of connection information. The content of the
 request should be JSON encoded. For example, the following json file
 can be published using curl.

```
> cat publish.json
{
 "connections":[
  {
   "connection_type":0,
   "data_type":"TPSet",
   "uid":"DRO-000-tp_to_trigger",
   "uri":"tcp://192.168.1.100:1234"
  },
  {
   "connection_type":0,
   "data_type":"TPSet",
   "uid":"DRO-001-tp_to_trigger",
   "uri":"tcp://192.168.1.100:1235"
  }
 ],
 "partition":"ccTest"
}

> curl -d @publish.json -H "content-type: application/json" \
    http://connection-flask.connections:5000/publish
```

### /getconnection/<partition> 
This uri returns a list of connections matching the 'uid_regex' and
'data_type' specified in the JSON encoded request.

```
curl -d '{"uid_regex":"DRO.*","data_type":"TPSet"}' \
    -H "content-type: application/json" \
     http://connection-flask.connections:5000/getconnection/ccTest
[{"uid": "DRO-000-tp_to_trigger", "uri": "tcp://192.168.1.100:1234", "connection_type": 0, "data_type": "TPSet"}, {"uid": "DRO-001-tp_to_trigger", "uri": "tcp://192.168.1.100:1235", "connection_type": 0, "data_type": "TPSet"}]
```


### /retract
This uri should be used to remove published connections. The request should be JSON encoded with the keys "partition" and "connections" with the latter being an array of "connection_id" and "data_type" values.


### /retract-partition
This uri should be used to remove all published connections from the
given partition. The request should be a urlencoded form with one field "partition" naming the partition to be retracted.

## Running the server locally from the command line
 To just run a local test, the server can be started from within the dbt-pyenv environment as shown below:
 ```
 > export FLASK_APP=microservices/connection-service/connection-flask.py
 > python -m flask run
 ```

 The server is intended to be run under the Gunicorn web server. This
 is set up in the docker container but is not be available in the
 dunedaq release. To run interactivley without creating the container
 you can install the dependencies with

 ```
 'pip install -r requirements.txt'
 ```

 ```
 > gunicorn -b 0.0.0.0:5000 --workers=1 --worker-class=gthread --threads=2 \
        --timeout 5000000000 --log-level=debug connection-flask:app
 ```