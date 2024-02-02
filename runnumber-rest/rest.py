<<<<<<< HEAD
#!/usr/bin/env python3
=======
__title__ = "NP04 run number"
__author__ = "Roland Sipos"
__credits__ = [""]
__version__ = "0.0.1"
__maintainers__ = ["Roland Sipos", "Pierre Lasorak", "Tiago Alves"]
__emails__ = ["roland.sipos@cern.ch", "plasorak@cern.ch", "tiago.alves20@imperial.ac.uk"]


import flask
from flask import Flask

from flask_restful import Api, Resource
from flask_httpauth import HTTPBasicAuth

import queries
import backend as db
from authentication import auth

>>>>>>> develop
'''
Main app

To control set the following environment variables:
DATABASE_URI - URI for sqlalchemy to use
DEBUG - set to TRUE for flask debugging
RUN_START - set to your starting run number, does not need to be changed after first launching as run number will be iterated from this initial value
'''
import os

from api import app, db

# setenv DEBUG=True to enable debug mode
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=DEBUG)