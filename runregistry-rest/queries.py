schema = ['RUN_NUMBER', 'START_TIME', 'STOP_TIME', 'DETECTOR_ID', 'RUN_TYPE', 'SOFTWARE_VERSION']

# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/getRunMeta/2 
getRunMeta = "select RUN_NUMBER, START_TIME, STOP_TIME, DETECTOR_ID, RUN_TYPE, SOFTWARE_VERSION from RUN_REGISTRY_META where RUN_NUMBER=:run_num"

# $ curl -u fooUsr:barPass -X GET -O -J np04-srv-021:5005/runregistry/getRunBlob/2 
getRunBlob = "select FILENAME, CONFIGURATION from RUN_REGISTRY_META natural join RUN_REGISTRY_CONFIGS where RUN_NUMBER=:run_num" 

# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/getRunMetaLast/100 
getRunMetaLast = "select * from (select RUN_NUMBER, START_TIME, STOP_TIME, DETECTOR_ID, RUN_TYPE, SOFTWARE_VERSION from RUN_REGISTRY_META order by RUN_NUMBER desc) where ROWNUM<=:amount"

# $ curl -u fooUsr:barPass -F "file=@sspconf.tar.gz" -F "run_num=4" -F "det_id=foo" -F "run_type=bar" -X POST http://localhost:5005/runregistry/insertRun/
#insertRunRegistry = "insert into RUN_REGISTRY (RUN_NUMBER, START_TIME, STOP_TIME, DETECTOR_ID, RUN_TYPE, FILENAME, CONFIGURATION, SOFTWARE_VERSION) values (:run_num, CURRENT_TIMESTAMP, NULL, :det_id, :run_type, :filename, :config_blob, :software_version)"

# $ curl -u fooUsr:barPass -F "file=@sspconf.tar.gz" -F "run_num=4" -F "det_id=foo" -F "run_type=bar" -X POST http://localhost:5005/runregistry/insertRun/
insertRunRegistryMeta = "insert into RUN_REGISTRY_META (RUN_NUMBER, START_TIME, STOP_TIME, DETECTOR_ID, RUN_TYPE, FILENAME, SOFTWARE_VERSION) values (:run_num, CURRENT_TIMESTAMP, NULL, :det_id, :run_type, :filename, :software_version)"

insertRunRegistryBlob = "insert into RUN_REGISTRY_CONFIGS (RUN_NUMBER, CONFIGURATION) values (:run_num, :config_blob)"

# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/updateStopTime/2 
updateStopTime = "update RUN_REGISTRY_META set STOP_TIME=CURRENT_TIMESTAMP where RUN_NUMBER=:run_num and STOP_TIME is null"

