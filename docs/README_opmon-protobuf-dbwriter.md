`dbwriter.py` is the script responsible for taking the opmon messages via the OpMonSubscriber
and writing to an InfluxDB database so that the data can be displayed in a
grafana dashboard. To run it manually do:
```python dbwriter.py [options]```


# Running locally
The script can be run locally which can be useful to debug or start up quickly. After setting up a working area and cloning this repo, run:
```
python3 dbwriter.py
```
Passing the appropriate variables.
As this script requires opmonlibs and kafkaopmon, it has to be launched by a developing envirnoment.
It can run at the same time locally and in kubernetes.
