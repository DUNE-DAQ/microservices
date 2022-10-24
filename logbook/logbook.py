__author__ = "Jonathan Hancock"
__credits__ = ["J.Bracinik", "P.Lasorak"]
__version__ = "1.0.0"
__maintainer__ = "Jonathan Hancock"
__email__ = "jonathan.hancock@cern.ch"

import os
import argparse
import re
import json
from urllib import response

from authentication import auth
from credmgr import credentials
from elisa import ElisaLogbook
from flask import Flask, request
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
app.config['USER'] = (os.getenv("USERNAME")).rstrip("\n")
app.config['PASSWORD'] = (os.getenv("PASSWORD")).rstrip("\n")
app.config['PATH'] = "./logfiles/"
'''
try:
    app.config['HARDWARECONF'] = elisaconf[hard_var]   #A dictionary containing all the hardware-dependant configs
except:
    bad_string = hard_var + " is not a valid choice!"
    raise Exception(bad_string + hardware_string)
'''
'''
for key in keylist:
    #makes a login for every logbook in the config
    credentials.add_login(key, app.config['USER'], app.config['PASSWORD'])
'''
credentials.add_login("np04_coldbox", app.config['USER'], app.config['PASSWORD'])
credentials.change_user(app.config['USER'])

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
        run_number = int(request.form['run_num'])
    except:
        error = "Run number is not an integer!"
        return error, 400

    try:
        file_path = app.config["PATH"] + f"_{run_number}_{request.form['run_type']}.txt"
        f = open(file_path, "w")
        f.write(f"-- User {request.form['author']} started a run {run_number}, of type {request.form['run_type']} --\n")
        f.write(request.form['author']+": "+request.form['message']+"\n")
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
        file_path = app.config["PATH"]+f"_{request.form['run_num']}_{request.form['run_type']}.txt"
    except Exception as e:
            return str(e), 400

    if os.path.exists(file_path):
        f = open(file_path, "a")
    else:
        error = "File not found!"
        return error, 404

    f.write(request.form['author']+": "+request.form['message']+"\n")
    f.close()
    rstring = "Logfile updated at " + file_path + "\n"
    return rstring, 200

# $ curl --user fooUsr:barPass -d "author=jsmith&message=foo&run_num=1&run_type=test" -X PUT http://localhost:5005/v1/fileLogbook/message_on_stop/
@app.route('/v1/fileLogbook/message_on_stop/', methods=["PUT"])
@auth.login_required
def Fmessage_on_stop():
    try:
        file_path = app.config["PATH"]+f"_{request.form['run_num']}_{request.form['run_type']}.txt"
    except Exception as e:
        return str(e), 400

    if os.path.exists(file_path):
        f = open(file_path, "a")
    else:
        error = "File not found!"
        return error, 404

    f.write(f"-- User {request.form['author']} stopped the run {request.form['run_num']}, of type {request.form['run_type']} --\n")
    f.write(request.form['author']+": "+request.form['message']+"\n")
    f.close()
    rstring = "Log stopped at " + file_path + "\n"
    return rstring, 200


#The second (preferred) type of logging is elisaLogbook, which sends the logs off to an external database.

# $ curl --user fooUsr:barPass -d "apparatus_id=np02_coldbox&author=jsmith&message=foo&run_num=1&run_type=TEST" -X POST http://localhost:5005/v1/elisaLogbook/message_on_start/
@app.route('/v1/elisaLogbook/message_on_start/', methods=["POST"])
@auth.login_required
def message_on_start():
    conf = elisaconf[request.form['apparatus_id']]
    logbook = ElisaLogbook("foo", conf)

    text = f"<p>User {request.form['author']} started run {request.form['run_num']} of type {request.form['run_type']}</p>"
    if request.form['message'] != "":
        text += "\n<p>"+request.form['author']+": "+request.form['message']+"</p>"
    text += "\n<p>log automatically generated by NanoRC.</p>"
    
    title = f"{request.form['author']} started new run {request.form['run_num']} ({request.form['run_type']})"

    try:
        thread_id = logbook._start_new_message_thread(subject=title, body=text, command='start', author=request.form['author'])
    except Exception as e:
        return str(e), 500
    
    return f"Message thread started successfully with ID {thread_id}\n", 201

# $ curl --user fooUsr:barPass -d "apparatus_id=np02_coldbox&author=jsmith&message=foo&thread_id=12345" -X PUT http://localhost:5005/v1/elisaLogbook/add_message/
@app.route('/v1/elisaLogbook/add_message/', methods=["PUT"])
@auth.login_required
def add_message():
    conf = elisaconf[request.form['apparatus_id']]
    logbook = ElisaLogbook("foo", conf)

    if request.form['message'] != "":
            text = "<p>"+request.form['author']+": "+request.form['message']+"</p>"
            try:
                logbook._send_message(subject="User comment", body=text, command='message', author=request.form['author'], thread_id=request.form['thread_id'])
            except Exception as e:
                return str(e), 500
            return "Message added successfully \n", 200
    else:
        error = "Message cannot be empty! \n"
        return error, 400

# $ curl --user fooUsr:barPass -d "apparatus_id=np02_coldbox&author=jsmith&message=foo&run_num=1&run_type=TEST&thread_id=12345" -X PUT http://localhost:5005/v1/elisaLogbook/message_on_stop/
@app.route('/v1/elisaLogbook/message_on_stop/', methods=["PUT"])
@auth.login_required
def message_on_stop():
    conf = elisaconf[request.form['apparatus_id']]
    logbook = ElisaLogbook("foo", conf)

    text = f"<p>User {request.form['author']} finished run {request.form['run_num']}</p>"
    if request.form['message']!="":
        text = "\n<p>"+request.form['author']+": "+request.form['message']+"</p>"
    text += "\n<p>log automatically generated by NanoRC.</p>"
    
    title = f"{request.form['author']} ended run {request.form['run_num']} ({request.form['run_type']})"
    try:
        logbook._send_message(subject=title, body=text, command='stop', author=request.form['author'], thread_id=request.form['thread_id'])
    except Exception as e:
        return str(e), 500
    return "Message thread stopped successfully \n", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
