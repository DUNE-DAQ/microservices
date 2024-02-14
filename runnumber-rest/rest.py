#!/usr/bin/env python3
"""
Main app

To control set the following environment variables:
DATABASE_URI - URI for sqlalchemy to use
DEBUG - set to TRUE for flask debugging
RUN_START - set to your starting run number, does not need to be changed after first launching as run number will be iterated from this initial value
DATABASE_TYPE - set to the type of database you want to use, default is postgresql
DEPLOYMENT_ENV - set to the environment you are deploying to, default is DEV
"""
import os

from api import app, db

# setenv DEBUG=True to enable debug mode
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=DEBUG)
