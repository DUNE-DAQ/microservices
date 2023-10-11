# Installation steps
For Oracle, you need the following packages installed on the host.

```
oracle-instantclient12.1-devel
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
python rest.py
```
or, to use Postgres:
```
python rest.py -p
```

# Authentication
You need the file `credentials.py` in the same directory as `backend.py`, this file needs to be of the form:
```
dburi='the_db_uri'
user='the_username'
password='the_password'
```
