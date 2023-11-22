import flask
import os
import sys
from flask import Flask

from flask_restful import Api, Resource
from flask_httpauth import HTTPBasicAuth

from authentication import auth

postgres = True

#temporary until I figure out what is wrong
import backends.pg_queries as queries
import backends.pg_backend as db

# if "-p" in sys.argv or os.environ.get("RGDB", None):
#     import backend.pg_queries as queries
#     import backend.pg_backend as db

#     postgres = True
# else:
#     import backend.ora_queries as queries
#     import backend.ora_backend as db

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


from sqlalchemy import create_engine, ForeignKey, Column, TIMESTAMP, Boolean, String, Integer, CHAR, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database

engine = create_engine('postgresql+psycopg2://{DUNE_runservices.postgresql_database_username}:{DUNE_runservices.postgresql_database_password}@{DUNE_runservices.postgresql_release_name}.{DUNE_runservices.namespace}.svc:5432/{DUNE_runservices.postgresql_database_name}')
if not database_exists(engine.url):
    print('Error: No database exists')
Session = sessionmaker(bind=engine)
session = Session()

# if not engine.dialect.has_table(engine, RunNumber(Base)):
metadata = MetaData()
class RunNumber():
    #__tablename__ = "run_schema.run_number"
    rn = Column("rn", Integer, primary_key=True, nullable=False)
    start_time = Column("start_time", TIMESTAMP(6), nullable=False)
    flag = Column("flag", Boolean, nullable=False)
    stop_time = Column("stop_time", TIMESTAMP(6))
new_run_number = RunNumber(rn=1000000, flag=True)
session.add(new_run_number)
session.commit()
        
metadata.create_all(engine)
session.close()
