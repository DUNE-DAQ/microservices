# Connection-service

 This service provides a very simple flask based
server to serve connection information to DAQ applications.

## Installation

 Build the docker image
```
docker buildx build --tag connection-service:0.0.0 .
```

 Apply the kubernetes manifest from connection-service.yaml. This
 should start a service called connection-flask in the namespace
 connections.

```
kubectl apply -f connection-service.yaml
```

## REST interface

  The server reponds to the following uris

```
http://connection-flask.connections:5000/publish
```

 Allows publication of connection information. Requires the parameter
'partition' with the name of the application's partition and either
'endpoint' and 'uri' to associate an endpoint with a uri, or
'connection' from which the endpoint and uri will be extracted. The
values of the 'endpoint', 'uri' and 'connection' parameters should be
set to a JSON string.  When setting from a connection, the endpoint is
extracted from the 'bind_endpoint' item and the uri from the 'uri'
item.

```
curl http://connection-flask.connections:5000/getendpoint/<partition> 
```

This uri returns a list of uris and a connection type associated with
the endpoint specification given in the required parameter
'endpoint'. fields within the endpoint JSON can be wild carded to
select all of a set of connections.

```
curl http://connection-flask.connections:5000/retract
```

This uri should be used to remove a published endpoint or connection
definition.

```
curl http://connection-flask.connections:5000/retract-partition
```

This uri should be used to remove all published endpoints and connection
definitions from the given partition.

