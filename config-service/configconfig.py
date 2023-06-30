import os

mongo_host=os.environ.get('MONGO_HOST', 'localhost')
mongo_port=os.environ.get('MONGO_PORT', '27017')
mongo_user=os.environ.get('MONGO_USER','')
mongo_pass=os.environ.get('MONGO_PASS','')
mongo_db=os.environ.get('MONGO_DBNAME','daqconfigdb')
logfile='/tmp/config-archiver.log'
service_host='localhost'
service_port=5003
