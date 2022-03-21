#!/bin/bash
sed -i -e "s%MONGO_HOST%${MONGO_HOST}%g" configconfig.py
sed -i -e "s%MONGO_PORT%${MONGO_PORT}%g" configconfig.py
sed -i -e "s%MONGO_USER%${MONGO_USER}%g" configconfig.py
sed -i -e "s%MONGO_PASS%${MONGO_PASS}%g" configconfig.py

exec gunicorn -b 0.0.0.0:5003 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug conf-service:app
