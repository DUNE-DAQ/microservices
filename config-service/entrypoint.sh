#!/bin/bash

echo "You should probably define env vars for:"
echo " MONGO_HOST, MONGO_PORT, MONGO_USER, MONGO_PASS, MONGO_DBNAME"

exec gunicorn -b 0.0.0.0:5003 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug conf-service:app
