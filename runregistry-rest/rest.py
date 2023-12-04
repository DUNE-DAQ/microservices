#!/usr/bin/env python3
"""
Main app

To control set the following environment variables:
DATABASE_URI - URI for sqlalchemy to use
DEBUG - set to TRUE for flask debugging
"""
import os

from api import app
from database import db

if __name__ == "__main__":
    # setenv DEBUG=True to enable debug mode    
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=5005, debug=DEBUG)

# As a testserver.
# app.run(host= '0.0.0.0', port=5000, debug=True)
# Normally spawned by gunicorn
