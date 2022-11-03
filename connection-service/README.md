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

---
> kubectl exec gordon-test -i -t -- bash
[root@gordon-test /]# curl http://connection-flask.connections:5000
<h1>Dump of configuration dictionary</h1>[root@gordon-test /]# 
[root@gordon-test /]#
---

## REST interface

  The server reponds to the following uris

```
http://connection-flask.connections:5000/publish
```

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

```
curl http://connection-flask.connections:5000/getconnection/<partition> 
```

This uri returns a list of connections matchin the 'uid_regex' and
'data_type' specified in the JSON encoded request.

```
curl -d '{"uid_regex":"DRO.*","data_type":"TPSet"}' \
    -H "content-type: application/json" \
     http://connection-flask.connections:5000/getconnection/ccTest
[{"uid": "DRO-000-tp_to_trigger", "uri": "tcp://192.168.1.100:1234", "connection_type": 0, "data_type": "TPSet"}, {"uid": "DRO-001-tp_to_trigger", "uri": "tcp://192.168.1.100:1235", "connection_type": 0, "data_type": "TPSet"}]
```


```
curl http://connection-flask.connections:5000/retract
```

This uri should be used to remove a published connections.

```
curl http://connection-flask.connections:5000/retract-partition
```

This uri should be used to remove all published connections from the
given partition.

