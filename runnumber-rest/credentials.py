import os

dbhost=os.environ.get('DB_HOSTNAME', 'localhost')
port=os.environ.get('DB_PORT', '5432')
username=os.environ.get('DB_USERNAME', 'runregistry')
password=os.environ.get('DB_PASSWORD', '')
database=os.environ.get('DB_NAME', 'runregistry')
