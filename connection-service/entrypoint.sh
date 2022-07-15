#!/bin/bash

exec gunicorn -b 0.0.0.0:5000 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug connection-flask:app
