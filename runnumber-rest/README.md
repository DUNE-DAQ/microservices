# Installation steps
You need the following package (from the "CERN Only" repository) installed on the host:
```
oracle-instantclient12.1-devel
oracle-instantclient-tnsnames.ora
```

Then, create the virtual environment:
```
python3 -m venv env
source env/bin/activate
python -m pip install -r requirements.txt
```

# Running the server
Once in venv:
```
python3 rest.py
```
# Authentication
You need the file `credentials.py` in the same directory as `backend.py`, this file needs to be of the form:
```
dburi='the_db_uri'
user='the_username'
password='the_password'
```
