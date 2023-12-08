`dbwriter.py` is the script responsible for taking the ERS messages via the ERSSubscriber
and writing to a postgreSQL database so that the messages can be displayed in a
grafana dashboard. The secrets to connect to the database are obtained from
environment variables. To run it manually do:
```python dbwriter.py [options]```
and if the env variables are set, it should start printing the messages that it
is receiving and writing to the database.

# Deploying on kubernetes
First, we need to make the secrets. Create a yaml file `ers-secret.yaml` containing the secrets:
```
apiVersion: v1
kind: Secret
metadata:
  name: ers-secret
  namespace: monitoring
type: Opaque
data:
  ERS_DBWRITER_HOST:
  ERS_DBWRITER_PORT:
  ERS_DBWRITER_USER:
  ERS_DBWRITER_PASS:
  ERS_DBWRITER_NAME:
```
where after each of the env variables (`ERS_DBWRITER_XXXX`) the secret goes in base64 form (can be obtained by doing `echo -n "secret" | base64`). To add the secrets run 
```
kubectl apply -f ers-secret.yaml
```
If all went well when we do `kubectl get secrets` we should see something like
```
NAME         TYPE     DATA   AGE
ers-secret   Opaque   5      37m
```
Once the secrets are set, do `kubectl apply -f ersdbwriter.yaml`.

We can get the pod name by doing `kubectl -n monitoring get pods` and then it will show something like
```
NAME                           READY   STATUS    RESTARTS   AGE
erskafka-7dfdf88864-4mwvd      1/1     Running   0          15m
```
where the important part is that `STATUS` is `Running`


# Running locally
The script can also be run locally which can be useful to debug or start up quickly. After setting up a working area and cloning this repo, run:
```
python3 dbwriter.py
```
Passing the appropriate variables. 
As this script requires ers and erskafak, it has to be launched by a developing envirnoment.
It can run at the same time locally and in kubernetes.

