import os
from datetime import datetime

import flask
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy

from authentication import auth
from sqlalchemy import func

__all__ = ["app", "api", "db"]

app = flask.Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URI", "sqlite:////tmp/test.sqlite"
)

db = SQLAlchemy(app)
api = Api(app)

from database import RunNumber


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
                db.session.execute(db.select(func.max(RunNumber.rn))).scalar_one()
            )
        except Exception as e:
            (err_obj,) = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        print(f"getRunNumber: result {rowRes}")
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
            # if we start at a higher number
            # the primary key sequence may not match
            current_max_run = db.session.execute(
                db.select(func.max(RunNumber.rn))
            ).scalar_one()
            current_max_run += 1
            run = RunNumber(rn=current_max_run)
            db.session.add(run)
            db.session.commit()
            rowRes.append(current_max_run)
        except Exception as e:
            (err_obj,) = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        print(f"getNewtRunNumber: result {rowRes}")
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
        print(f"updateStopTimestamp: arg {runNum}")
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
        print(f"updateStopTimestamp: result {rowRes}")
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp


@app.route("/")
def index():
    """basic self test"""
    return "It works"
