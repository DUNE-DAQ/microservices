# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/getRunMeta/2 
getRunMeta = "select RUN_NUMBER, START_TIME, STOP_TIME, DETECTOR_ID, RUN_TYPE from RUN_REGISTRY where RUN_NUMBER=:run_num"

# $ curl -u fooUsr:barPass -X GET -O -J np04-srv-021:5005/runregistry/getRunBlob/2 
getRunBlob = "select FILENAME, CONFIGURATION from RUN_REGISTRY where RUN_NUMBER=:run_num" 

# $ curl -u fooUsr:barPass -F "file=@sspconf.tar.gz" -F "run_num=4" -F "det_id=foo" -F "run_type=bar" -X POST http://localhost:5005/runregistry/insertRun/
insertRunRegistry = "insert into RUN_REGISTRY (RUN_NUMBER, START_TIME, STOP_TIME, DETECTOR_ID, RUN_TYPE, FILENAME, CONFIGURATION) values (:run_num, CURRENT_TIMESTAMP, NULL, :det_id, :run_type, :filename, :config_blob)"

# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/updateStopTime/2 
updateStopTime = "update RUN_REGISTRY set STOP_TIME=CURRENT_TIMESTAMP where RUN_NUMBER=:run_num and STOP_TIME is null"

