#!/bin/bash

cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables "DATABASE_URI"

<<<<<<< HEAD
if [[ ! -d /uploads ]]; then
    mkdir --mode=1777 /uploads
else
    chmod 1777 /uploads
fi
=======

mkdir --mode=1777 uploads

export LD_LIBRARY_PATH=/usr/lib/oracle/12.1/client64/lib/:$LD_LIBRARY_PATH
>>>>>>> develop

exec gunicorn -b 0.0.0.0:5005 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug rest:app
