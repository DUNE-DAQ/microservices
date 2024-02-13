#!/bin/bash

cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables "DATABASE_URI" 

export LD_LIBRARY_PATH=/usr/lib/oracle/12.1/client64/lib/:$LD_LIBRARY_PATH

exec gunicorn -b 0.0.0.0:5000 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug rest:app
