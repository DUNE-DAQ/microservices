# Installation steps
Create the virtual environment:
```
python3 -m venv env
source env/bin/activate
python -m pip install -r requirements.txt
```

For NP04 this uses the pure python Oracle thin client.

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
