import logging, copy, os, tempfile
from flask import Flask
from credmgr import credentials
from credmgr import CERNSessionHandler

from elisa_client_api.elisa import Elisa
from elisa_client_api.searchCriteria import SearchCriteria
from elisa_client_api.messageInsert import MessageInsert
from elisa_client_api.messageReply import MessageReply
from elisa_client_api.exception import *

class ElisaLogbook:
    '''
    This class collects data relating the logbook into one object, and uses it to connect to ELisA.
    '''
    def __init__(self, configuration, handler):
        self.elisa_arguments = {"connection": configuration['connection']}
        self.website = configuration['website']
        self.message_attributes = configuration['attributes']
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.info(f'ELisA logbook connection: {configuration["website"]} (API: {configuration["connection"]})')
        self.session_handler = handler

    def start_new_thread(self, subject:str, body:str, command:str, author:str):
        elisa_arg = copy.deepcopy(self.elisa_arguments)
        elisa_user = credentials.get_login('elisa')

        with tempfile.NamedTemporaryFile() as tf:
            try:
                sso = {"ssocookie": self.session_handler.generate_elisa_cern_cookie(self.website, tf.name)}
                elisa_arg.update(sso)
                elisa_inst = Elisa(**elisa_arg)
                answer = None
                self.log.info("ELisA logbook: Creating a new message thread")
                message = MessageInsert()
                message.author = author
                message.subject = subject
                for attr_name, attr_data in self.message_attributes[command].items():
                    if attr_data['set_on_new_thread']:
                        setattr(message, attr_name, attr_data['value'])
                message.systemsAffected = ["DAQ"]
                message.body = body
                answer = elisa_inst.insertMessage(message)

            except ElisaError as ex:
                self.log.error(f"ELisA logbook: {str(ex)}")
                self.log.error(answer)
                raise ex

            self.log.info(f"ELisA logbook: Sent message (ID{answer.id})")
            return answer.id

    def reply(self, body:str, command:str, author:str, id:int):
        elisa_arg = copy.deepcopy(self.elisa_arguments)
        elisa_user = credentials.get_login('elisa')

        with tempfile.NamedTemporaryFile() as tf:
            try:
                sso = {"ssocookie": self.session_handler.generate_elisa_cern_cookie(self.website, tf.name)}
                elisa_arg.update(sso)
                elisa_inst = Elisa(**elisa_arg)
                answer = None
                self.log.info(f"ELisA logbook: Answering to message ID{id}")
                message = MessageReply(id)
                message.author = author
                message.systemsAffected = ["DAQ"]
                for attr_name, attr_data in self.message_attributes[command].items():
                    if attr_data['set_on_reply']:
                        setattr(message, attr_name, attr_data['value'])
                message.body = body
                answer = elisa_inst.replyToMessage(message)

            except ElisaError as ex:
                self.log.error(f"ELisA logbook: {str(ex)}")
                self.log.error(answer)
                raise ex

            self.log.info(f"ELisA logbook: Sent message (ID{answer.id}), replying to ID{id}")
            return answer.id

