#!/bin/bash

cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables "DATABASE_URI"

if [[ ! -d ./uploads ]]; then
    mkdir ./uploads
fi

exec gunicorn -b 0.0.0.0:5005 --workers=1 --worker-class=gevent --timeout 5000000000 --log-level=debug rest:app
