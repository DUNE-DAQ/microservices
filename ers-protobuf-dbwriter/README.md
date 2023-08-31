`dbwriter.py` is the script responsible for taking the ERS messages from the broker
and writing to a postgreSQL database so that the messages can be displayed in a
grafana dashboard. The secrets to connect to the database are obtained from
environment variables. To run it manually do:
```python dbwriter.py```
and if the env variables are set, it should start printing the messages that it
is receiving and writing to the database.

Long term, it may be preferable to use `telegraf` as a kafka to postgresql bridge or KafkaConnect for postgresql to avoid longterm code maintance here.

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

If needed, the logs can be accessed by
```
kubectl logs erskafka-7dfdf88864-4mwvd -n monitoring
```

# Running locally
The script can also be run locally which can be useful to debug or start up quickly. After setting up a working area and cloning this repo, run:
```
pip install -r requirements.txt
export ERS_DBWRITER_HOST=host
export ERS_DBWRITER_PORT=port
export ERS_DBWRITER_USER=user
export ERS_DBWRITER_PASS=pass
export ERS_DBWRITER_NAME=name
python3 dbwriter.python3
```
where the values of the env variables have to be substituted by their actual values. While running, the messages received from kafka will be printed as they arrive: 
```
$ python3 dbwriter.py
ConsumerRecord(topic='erskafka-reporting', partition=0, offset=3156, timestamp=1667205932928, timestamp_type=0, key=None, value=b'{"application_name":"trigger","chain":0,"cwd":"/nfs/sw/jcarcell/N22-10-30","file_name":"/tmp/root/spack-stage/spack-stage-trigger-N22-10-30-mt5md7ywovoz27didgrn5grbucv623da/spack-src/plugins/ModuleLevelTrigger.cpp","function_name":"void dunedaq::trigger::ModuleLevelTrigger::do_start(const nlohmann::json&)","group_hash":987365171,"host_name":"np04-srv-022","issue_name":"trigger::TriggerStartOfRun","line_number":130,"message":"Start of run 293287","package_name":"unknown","params":["runno: 293287"],"partition":"jcarcell","process_id":1802216,"qualifiers":["unknown"],"severity":"INFO","thread_id":1802245,"time":1667205932928,"usecs_since_epoch":1667205932928264,"user_id":141008,"user_name":"jcarcell"}', headers=[], checksum=None, serialized_key_size=-1, serialized_value_size=707, serialized_header_size=-1)
```
It can run at the same time locally and in kubernetes.

