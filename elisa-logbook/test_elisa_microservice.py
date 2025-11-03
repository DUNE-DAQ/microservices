import getpass
import json
import multiprocessing
import os
import pytest
import requests
import socket
import time

from elisa import ElisaLogbook
from credmgr import CERNSessionHandler, credentials


@pytest.fixture
def elisa_logbook_config():
    with open('elisaconf.json', 'r') as f:
        return json.load(f)


@pytest.fixture
def elisa_microservice_config():
    with open(os.path.expanduser('~/.drunc.json'), 'r') as f:
        return json.load(f)


@pytest.fixture
def elisa_microservice_local_config(): # a configuration to start the microservice locally
    with open(os.path.expanduser('~/.drunc.json'), 'r') as f:
        data = json.load(f)
        updated_data = {}
        port = 61263
        for key, values in data['elisa_configuration'].items():
            values['socket'] = f'http://0.0.0.0:{port}'
            port += 1
            updated_data[key] = values
        data['elisa_configuration'] = updated_data
        return data


@pytest.fixture
def systems(request):
    return request.config.getoption("--system")


@pytest.fixture
def cern_session():
    user_var = os.getenv("USERNAME").strip("\n")
    pass_var = os.getenv("PASSWORD").strip("\n")
    credentials.add_login("elisa", user_var, pass_var, "CERN.CH")
    return CERNSessionHandler(user_var)


@pytest.fixture()
def local_microservice(elisa_microservice_local_config):

    def run_app(which_system):
        # Configure app for testing

        socket = elisa_microservice_local_config['elisa_configuration'][which_system]['socket']
        port = int(socket.split(':')[-1])
        host = ":".join(socket.split(':')[:-1])

        def run_with_env(*args, **kwargs):
            os.environ["HARDWARE"] = which_system
            from logbook import app
            app.config['TESTING'] = True
            app.run(*args, **kwargs)

        # Start Flask in a separate process
        process = multiprocessing.Process(
            target = run_with_env,
            kwargs = {
                'port': port,
                'host': host.replace('http://', '').replace('https://', ''),
                'debug': True,
            }
        )
        process.daemon = True
        process.start()

        # Give the server a moment to start
        time.sleep(1)
        return process

    return run_app


def test_elisa_configuration(
        systems,
        elisa_logbook_config):

    for system in systems:
        assert system in elisa_logbook_config

        system_config = elisa_logbook_config[system]

        assert 'connection' in system_config
        assert 'website' in system_config
        assert 'attributes' in system_config
        messages_kind = ['start', 'stop', 'message']

        for message_kind in messages_kind:
            assert message_kind in system_config['attributes']

            assert 'type'              in system_config['attributes'][message_kind]
            assert 'set_on_reply'      in system_config['attributes'][message_kind]['type']
            assert 'set_on_new_thread' in system_config['attributes'][message_kind]['type']
            assert 'value'             in system_config['attributes'][message_kind]['type']

            assert ('RunControl_MessageType' in system_config['attributes'][message_kind] or
                    'Automatic_Message_Type' in system_config['attributes'][message_kind])

            if 'RunControl_MessageType' in system_config['attributes'][message_kind]:
                assert 'set_on_reply'      in system_config['attributes'][message_kind]['RunControl_MessageType']
                assert 'set_on_new_thread' in system_config['attributes'][message_kind]['RunControl_MessageType']
                assert 'value'             in system_config['attributes'][message_kind]['RunControl_MessageType']

            elif 'Automatic_Message_Type' in system_config['attributes'][message_kind]:
                assert 'set_on_reply'      in system_config['attributes'][message_kind]['Automatic_Message_Type']
                assert 'set_on_new_thread' in system_config['attributes'][message_kind]['Automatic_Message_Type']
                assert 'value'             in system_config['attributes'][message_kind]['Automatic_Message_Type']


def test_elisa_logbook(
        systems,
        elisa_logbook_config,
        cern_session):

    for system in systems:

        elisa_logbook = ElisaLogbook(
            elisa_logbook_config[system],
            cern_session
        )
        assert elisa_logbook is not None
        thread_id = elisa_logbook.start_new_thread(
            "unit-test",
            "test_elisa_logbook: Ignore this message",
            "start",
            getpass.getuser(),
            ['DAQ']
        )
        assert thread_id is not None
        thread_id_response = elisa_logbook.reply(
            "test_elisa_logbook: Ignore this message",
            "stop",
            getpass.getuser(),
            ['DAQ'],
            thread_id
        )
        assert thread_id_response is not None


def test_elisa_microservice_conf(
        systems,
        elisa_microservice_config):

    assert "elisa_configuration" in elisa_microservice_config

    elisa_configuration = elisa_microservice_config["elisa_configuration"]

    for system in systems:
        assert system in elisa_configuration

        system_config = elisa_configuration[system]

        assert "socket"   in system_config
        assert "user"     in system_config
        assert "password" in system_config



def test_elisa_microservice_locally(
        systems,
        elisa_microservice_local_config,
        local_microservice):

    elisa_configuration = elisa_microservice_local_config["elisa_configuration"]

    for system in systems:
        lm = local_microservice(system)
        system_config = elisa_configuration[system]
        usvc_socket = system_config['socket'].replace('0.0.0.0', socket.gethostname())

        response = requests.get(usvc_socket + '/')
        response.raise_for_status()
        assert response.status_code == 200

        response = requests.post(
            usvc_socket + '/v1/elisaLogbook/new_message/',
            json={
                'title': 'unit-test',
                'body': 'test_elisa_microservice_locally: Ignore this message',
                'command': 'start',
                'author': getpass.getuser(),
                'systems': ['DAQ']
            },
            auth=(system_config['user'], system_config['password'])
        )
        response.raise_for_status()
        response_json = response.json()
        assert response_json['response'] == "Message thread started successfully"
        assert response_json['thread_id'] is not None
        response = requests.put(
            usvc_socket + '/v1/elisaLogbook/reply_to_message/',
            json={
                'id': response_json['thread_id'],
                'body': 'test_elisa_microservice_locally: Ignore this message',
                'command': 'stop',
                'author': getpass.getuser(),
                'systems': ['DAQ']
            },
            auth=(system_config['user'], system_config['password'])
        )
        response.raise_for_status()
        response_json = response.json()
        assert response_json['response'] == "Message thread replied successfully"

