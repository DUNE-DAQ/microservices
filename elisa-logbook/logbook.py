__author__ = "Jonathan Hancock"
__credits__ = ["J.Bracinik", "P.Lasorak"]
__version__ = "1.1.0"
__maintainer__ = "Jonathan Hancock"
__email__ = "jonathan.hancock@cern.ch"

import os
import argparse
import re
import json
from urllib import response

from authentication import auth
from credmgr import credentials, CERNSessionHandler
from elisa import ElisaLogbook
from flask import Flask, request, jsonify, make_response
from flask_restful import Api
from flask_caching import Cache

#Sets up the app and processes command line inputs
app = Flask(__name__)
cache = Cache(app)
api = Api(app)

#Converts the config json into a dictionary, and gets a list of the keys
with open('elisaconf.json') as json_file:
    elisaconf = json.load(json_file)
keylist = elisaconf.keys()
hardware_string = "Please choose from one of the following options:"
for key in keylist:
    hardware_string += " "
    hardware_string += key

#We use environment variables to pass data
user_var = (os.getenv("USERNAME")).rstrip("\n")
pass_var = (os.getenv("PASSWORD")).rstrip("\n")
hard_var = (os.getenv("HARDWARE")).rstrip("\n")
app.config['USER'] = user_var
app.config['PASSWORD'] = pass_var
app.config['PATH'] = "./logfiles/"
try:
    app.config['HARDWARECONF'] = elisaconf[hard_var]   #A dictionary containing all the hardware-dependant configs
except:
    bad_string = hard_var + " is not a valid choice!"
    raise Exception(bad_string + hardware_string)

credentials.add_login("elisa", app.config['USER'], app.config['PASSWORD'], "CERN.CH")
cern_auth = CERNSessionHandler(username = app.config['USER'])

logbook = ElisaLogbook(app.config['HARDWARECONF'], cern_auth)
#Main app
#The general principle is to replace the methods of each class with API methods
#The first type of logging is fileLogbook, which writes logs to a given file in the current working directory.

@app.route('/')
def index():
    return "<h1>Welcome to the logbook API!</h1>"

# $ curl --user fooUsr:barPass -d "author=jsmith&message=foo&run_num=1&run_type=test" -X POST http://localhost:5005/v1/fileLogbook/message_on_start/
@app.route('/v1/fileLogbook/message_on_start/', methods=["POST"])
@auth.login_required
def Fmessage_on_start():
    try:
        run_number = int(request.json['run_num'])
    except:
        error = "Run number is not an integer!"
        return error, 400

    try:
        file_path = app.config["PATH"]+f"_{run_number}_{request.json['run_type']}.txt"
        f = open(file_path, "w")
        f.write(f"-- User {request.json['author']} started a run {run_number}, of type {request.json['run_type']} --\n")
        f.write(request.json['author']+": "+request.json['message']+"\n")
        f.close()
        rstring = "Logfile started at " + file_path + "\n"
        return rstring, 201
    except Exception as e:
            return str(e), 400

# $ curl --user fooUsr:barPass -d "author=jsmith&message=foo&run_num=1&run_type=test" -X PUT http://localhost:5005/v1/fileLogbook/add_message/
@app.route('/v1/fileLogbook/add_message/', methods=["PUT"])
@auth.login_required
def Fadd_message():
    try:
        file_path = app.config["PATH"]+f"_{request.json['run_num']}_{request.json['run_type']}.txt"
    except Exception as e:
            return str(e), 400

    if os.path.exists(file_path):
        f = open(file_path, "a")
    else:
        error = "File not found!"
        return error, 404

    f.write(request.json['author']+": "+request.json['message']+"\n")
    f.close()
    rstring = "Logfile updated at " + file_path + "\n"
    return rstring, 200

# $ curl --user fooUsr:barPass -d "author=jsmith&message=foo&run_num=1&run_type=test" -X PUT http://localhost:5005/v1/fileLogbook/message_on_stop/
@app.route('/v1/fileLogbook/message_on_stop/', methods=["PUT"])
@auth.login_required
def Fmessage_on_stop():
    try:
        file_path = app.config["PATH"]+f"_{request.json['run_num']}_{request.json['run_type']}.txt"
    except Exception as e:
        return str(e), 400

    if os.path.exists(file_path):
        f = open(file_path, "a")
    else:
        error = "File not found!"
        return error, 404

    f.write(f"-- User {request.json['author']} stopped the run {request.json['run_num']}, of type {request.json['run_type']} --\n")
    f.write(request.json['author']+": "+request.json['message']+"\n")
    f.close()
    rstring = "Log stopped at " + file_path + "\n"
    return rstring, 200


#The second (preferred) type of logging is elisaLogbook, which sends the logs off to an external database.

# $ curl --user fooUsr:barPass -H "Content-Type: application/json" -d '{"author":"jhancock", "title":"Test", "body":"Testing the microservice", "command":"start", "systems":["daq"]}'  -X POST http://localhost:5005/v1/elisaLogbook/new_message/
@app.route('/v1/elisaLogbook/new_message/', methods=["POST"])
@auth.login_required
def new_message():
    print(request.json)
    if request.json.get('body', "") == "" or request.json.get('title', "") == "" or request.json.get('command', "") == "" or request.json.get('author', "") == "":
        resp = make_response(
            jsonify(
                response = "Body, title, command, author cannot be empty!",
                sent_data = request.json
            )
        )
        resp.status = 400
        resp.headers['mimetype'] = 'application/json'
        return resp
    try:
        sys_list = request.json.get('system', ['DAQ'])  #Defaults to DAQ since that's the most likely use case
        thread_id = logbook.start_new_thread(subject=request.json['title'], body=request.json['body'], command=request.json['command'], author=request.json['author'], systems=sys_list)
    except Exception as e:
        import traceback
        traceback.print_exc()
        stack = traceback.format_exc().split("\n")
        resp = make_response(jsonify(stacktrace = stack))
        resp.status = 500
        resp.headers['mimetype'] = 'application/json'
        return resp

    resp = make_response(jsonify(response = "Message thread started successfully", thread_id = thread_id))
    resp.status = 201
    resp.headers['mimetype'] = 'application/json'
    return resp


# $ curl --user fooUsr:barPass -H "Content-Type: application/json" -d '{"author":"jsmith", "body":"Testing the microservice", "command":"start", "systems":["daq"], "id": 9999}'  -X PUT http://localhost:5005/v1/elisaLogbook/reply_to_message/
@app.route('/v1/elisaLogbook/reply_to_message/', methods=["PUT"])
@auth.login_required
def reply_to_message():
    if request.json.get('body', "") == "" or request.json.get('command', "") == "" or request.json.get('author', "") == "" or request.json.get('id', "") == "":
        resp = make_response(
            jsonify(
                response = "Body, command, author or id cannot be empty!",
                sent_data = request.json
            )
        )
        resp.status = 400
        resp.headers['mimetype'] = 'application/json'
        return resp
    try:
        sys_list = request.json.get('system', ['DAQ'])
        thread_id = logbook.reply(body=request.json['body'], command=request.json['command'], author=request.json['author'], systems=sys_list, id=request.json['id'])
    except Exception as e:
        import traceback
        traceback.print_exc()
        stack = traceback.format_exc().split("\n")
        resp = make_response(jsonify(stacktrace = stack))
        resp.status = 500
        resp.headers['mimetype'] = 'application/json'
        return resp

    resp = make_response(jsonify(response = "Message replied successfully", thread_id = thread_id))
    resp.status = 201
    resp.headers['mimetype'] = 'application/json'
    return resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
