#!/bin/bash

echo "You should probably define env vars for:"
echo "  DB_HOSTNAME, DB_PORT, DB_NAME, DB_USERNAME, DB_PASSWORD"

exec gunicorn -b 0.0.0.0:5005 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug rest:app
