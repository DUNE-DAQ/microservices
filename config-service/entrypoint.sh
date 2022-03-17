#!/bin/bash

sed -i "s/'MONGO_CONNECTION_STRING'/'${MONGO_CONNECTION_STRING}'/g" /configconfig.py

exec gunicorn -b 0.0.0.0:5003 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug conf-service:app
