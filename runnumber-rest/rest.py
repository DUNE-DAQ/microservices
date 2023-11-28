#!/usr/bin/env python3
"""
Main app

To control set the following environment variables:
DATABASE_URI - URI for sqlalchemy to use
DEBUG - set to TRUE for flask debugging
"""
import os
from datetime import datetime

import flask
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, desc

from authentication import auth

db = SQLAlchemy()


class RunNumber(db.Model):
    """
    The run number object in the database

    TODO: how to specify start value for auto increment of run id
    """

    rn = Column("rn", Integer, primary_key=True, autoincrement=True, nullable=False)
    flag = Column("flag", Boolean, nullable=False, default=False)
    start_time = Column(
        "start_time", TIMESTAMP(6), nullable=False, default=datetime.now
    )
    stop_time = Column("stop_time", TIMESTAMP(6), nullable=True)


app = flask.Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URI", "sqlite:///tmp/db.sqlite"
)

api = Api(app)


@api.resource("/runnumber/get")
class getRunNumber(Resource):
    """
    should return the run number in format: XXXXXXX
    """

    @auth.login_required
    def get(self):
        rowRes = []
        try:
            rowRes.append(
                db.session.execute(
                    db.select(RunNumber).order_by(desc(RunNumber.rn))
                ).scalar_one()
            )
        except Exception as e:
            (err_obj,) = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        print(rowRes)
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp


@api.resource("/runnumber/getnew")
class getNewtRunNumber(Resource):
    """
    create a new run in the database
    should return the run number in format: XXXXXXX
    """

    @auth.login_required
    def get(self):
        rowRes = []
        try:
            run = RunNumber()
            db.session.add(run)
            db.session.commit()
            rowRes.append(
                db.session.execute(
                    db.select(RunNumber).order_by(desc(RunNumber.rn))
                ).scalar_one()
            )
        except Exception as e:
            (err_obj,) = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        print(rowRes)
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp


@api.resource("/runnumber/updatestop/<int:runNum>")
class updateStopTimestamp(Resource):
    """
    set the stop time for the run
    should return the times in format: XXXXXXX
    """

    @auth.login_required
    def get(self, runNum):
        rowRes = []
        try:
            run = db.session.execute(
                db.select(RunNumber).filter_by(rn=runNum)
            ).scalar_one()
            run.stop_time = datetime.now()
            db.session.commit()
            rowRes.extend((run.start_time, run.stop_time))
        except Exception as e:
            (err_obj,) = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        print(rowRes)
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp


@app.route("/")
def index():
    """basic self test"""
    return "It works"


if __name__ == "__main__":
    # setenv DEBUG=True to enable debug mode
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=5000, debug=DEBUG)
