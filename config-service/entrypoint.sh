#!/bin/bash

cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables "MONGO_HOST MONGO_PORT MONGO_USER MONGO_PASS MONGO_DBNAME"

exec gunicorn -b 0.0.0.0:5003 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug conf-service:app
