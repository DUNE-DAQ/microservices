schema = [
    "RUN_NUMBER",
    "START_TIME",
    "STOP_TIME",
    "DETECTOR_ID",
    "RUN_TYPE",
    "SOFTWARE_VERSION",
]

# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/getRunMeta/2
getRunMeta = "select RUN_NUMBER, START_TIME, STOP_TIME, DETECTOR_ID, RUN_TYPE, SOFTWARE_VERSION from RUN_SCHEMA.RUN_REGISTRY_META where RUN_NUMBER=%(run_num)s"

# $ curl -u fooUsr:barPass -X GET -O -J np04-srv-021:5005/runregistry/getRunBlob/2
getRunBlob = "select FILENAME, CONFIGURATION from RUN_SCHEMA.RUN_REGISTRY_META natural join RUN_SCHEMA.RUN_REGISTRY_CONFIGS where RUN_NUMBER=%(run_num)s"

# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/getRunMetaLast/100
getRunMetaLast = "select * from (select RUN_NUMBER, START_TIME, STOP_TIME, DETECTOR_ID, RUN_TYPE, SOFTWARE_VERSION from RUN_SCHEMA.RUN_REGISTRY_META order by RUN_NUMBER desc) DUMMY limit %(amount)s"

# $ curl -u fooUsr:barPass -F "file=@sspconf.tar.gz" -F "run_num=4" -F "det_id=foo" -F "run_type=bar" -X POST http://localhost:5005/runregistry/insertRun/
insertRunRegistryMeta = "insert into RUN_SCHEMA.RUN_REGISTRY_META (RUN_NUMBER, START_TIME, STOP_TIME, DETECTOR_ID, RUN_TYPE, FILENAME, SOFTWARE_VERSION) values (%(run_num)s, LOCALTIMESTAMP(6), NULL, %(det_id)s, %(run_type)s, %(filename)s, %(software_version)s)"

insertRunRegistryBlob = "insert into RUN_SCHEMA.RUN_REGISTRY_CONFIGS (RUN_NUMBER, CONFIGURATION) values (%(run_num)s, %(config_blob)s)"

# $ curl -u fooUsr:barPass -X GET np04-srv-021:5005/runregistry/updateStopTime/2
updateStopTime = "update RUN_SCHEMA.RUN_REGISTRY_META set STOP_TIME=CURRENT_TIMESTAMP where RUN_NUMBER=%(run_num)s and STOP_TIME is NULL"
