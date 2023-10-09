#!/bin/bash

cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables "ERS_DBWRITER_HOST ERS_DBWRITER_PORT ERS_DBWRITER_USER ERS_DBWRITER_PASS ERS_DBWRITER_NAME ERS_DBWRITER_KAFKA_BOOTSTRAP_SERVER"
    
python3 ./dbwriter.py
