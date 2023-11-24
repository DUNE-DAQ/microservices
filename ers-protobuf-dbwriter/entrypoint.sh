#!/bin/bash

cd $(dirname $0)
source ../entrypoint_functions.sh

ensure_required_variables "ERS_DBWRITER_HOST ERS_DBWRITER_PORT ERS_DBWRITER_USER ERS_DBWRITER_PASS ERS_DBWRITER_NAME ERS_DBWRITER_KAFKA_SERVER ERS_DBWRITER_KAFKA_PORT ERS_TABLE_NAME ERS_DBWRITER_KAFKA_TIMEOUT_MS ERS_DBWRITER_KAFKA_GROUP "
    
python3 ./dbwriter.py --subscriber-address $ERS_DBWRITER_KAFKA_SERVER  --subscriber-port $ERS_DBWRITER_KAFKA_PORT \
                      --subscriber-group $ERS_DBWRITER_KAFKA_GROUP --subscriber-timeout  $ERS_DBWRITER_KAFKA_TIMEOUT_MS  \
                      --db-address $ERS_DBWRITER_HOST  --db-port $ERS_DBWRITER_PORT \
                      --db-user $ERS_DBWRITER_USER  --db-password $ERS_DBWRITER_PASS \
                      --db-name $ERS_DBWRITER_NAME  --db-table $ERS_TABLE_NAME \
                      --debug False 
                      

