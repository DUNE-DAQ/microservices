import flask
from flask import Flask

from flask_restful import Api, Resource
from flask_httpauth import HTTPBasicAuth

import queries
import backend as db
from authentication import auth

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
