import flask
import os
import sys
from flask import Flask

from flask_restful import Api, Resource
from flask_httpauth import HTTPBasicAuth

from authentication import auth

postgres = False

if "-p" in sys.argv or os.environ.get("RGDB", None):
    import backend.pg_queries as queries
    import backend.pg_backend as db

    postgres = True
else:
    import backend.ora_queries as queries
    import backend.ora_backend as db

'''
Main app
'''
app = Flask(__name__)

api = Api(app)

@api.resource("/runnumber/get")
class getRunNumber(Resource):
    @auth.login_required
    def get(self):
        rowRes = []
        try:
            db.perform_query(queries.getRunNum, {}, rowRes)
        except Exception as e:
            err_obj, = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        print(rowRes)
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp

@api.resource("/runnumber/getnew")
class getNewtRunNumber(Resource):
    @auth.login_required
    def get(self):
        rowRes = []
        try:
            db.perform_transaction(queries.incrementRunNum, {})
            db.perform_query(queries.getRunNum, {}, rowRes)
        except Exception as e:
            err_obj, = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        print(rowRes)
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp

@api.resource("/runnumber/updatestop/<int:runNum>")
class updateStopTimestamp(Resource):
    @auth.login_required
    def get(self, runNum):
        rowRes = []
        try:
            db.perform_transaction(queries.updateStopTimestamp, {'runNum':runNum})
            db.perform_query(queries.getRunTime, {'runNum':runNum}, rowRes)
        except Exception as e:
            err_obj, = e.args
            print("Exception:", err_obj.message)
            resp = flask.make_response(flask.jsonify({"Exception": err_obj.message}))
            return resp
        print(rowRes)
        resp = flask.make_response(flask.jsonify(rowRes))
        return resp

@app.route('/')
def index():
    return "Best thing since sliced bread!"

if __name__ == '__main__':
    # As a testserver.
    # app.run(host='0.0.0.0', port=5000, debug=True)

    # Normally spawned by gunicorn
    app.run(host= '0.0.0.0', port=5000, debug=False)
