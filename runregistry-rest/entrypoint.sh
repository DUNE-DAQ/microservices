#!/bin/bash


cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables "DB_HOSTNAME DB_PORT DB_NAME DB_USERNAME DB_PASSWORD"


mkdir --mode=1777 uploads

export LD_LIBRARY_PATH=/usr/lib/oracle/12.1/client64/lib/:$LD_LIBRARY_PATH

exec gunicorn -b 0.0.0.0:5005 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug rest:app
