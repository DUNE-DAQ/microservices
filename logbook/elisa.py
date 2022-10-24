import logging, copy, os
from flask import Flask
from credmgr import credentials

from elisa_client_api.elisa import Elisa
from elisa_client_api.searchCriteria import SearchCriteria
from elisa_client_api.messageInsert import MessageInsert
from elisa_client_api.messageReply import MessageReply
from elisa_client_api.exception import *

class ElisaLogbook:
    '''
    This class collects data relating the logbook into one object, and uses it to connect to ELisA.
    '''
    def __init__(self, console, configuration):
        self.console = console  #This seems useless, so foo is passed to it in all instances
        self.elisa_arguments = {"connection": configuration['connection']}
        self.website = configuration['website']
        self.message_attributes = configuration['attributes']
        self.log = logging.getLogger(self.__class__.__name__)
        self.log.info(f'ELisA logbook connection: {configuration["website"]} (API: {configuration["connection"]})')
        #self.current_id = None
        #self.current_run = None
        #self.current_run_type = None
    '''
    def _start_new_message_thread(self):
        self.log.info("ELisA logbook: Next message will be a new thread")
        self.current_id = None
        self.current_run = None
        self.current_run_type = None
    '''

    def _start_new_message_thread(self, subject:str, body:str, command:str, author:str):
            if not (credentials.check_kerberos_credentials()):
                credentials.new_kerberos_ticket

            elisa_arg = copy.deepcopy(self.elisa_arguments)
            sso = {"ssocookie": credentials.generate_new_sso_cookie(self.website)}
            elisa_arg.update(sso)

            elisa_inst = Elisa(**elisa_arg)
            try:
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
            os.remove(sso['ssocookie']) 
            return(answer.id)

    def _send_message(self, subject:str, body:str, command:str, author:str, thread_id:int):
            if not (credentials.check_kerberos_credentials()):
                credentials.new_kerberos_ticket

            elisa_arg = copy.deepcopy(self.elisa_arguments)
            sso = {"ssocookie": credentials.generate_new_sso_cookie(self.website)}
            elisa_arg.update(sso)

            elisa_inst = Elisa(**elisa_arg)
            try:
                answer = None
                self.log.info(f"ELisA logbook: Answering to message ID{thread_id}")
                message = MessageReply(thread_id)
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
            
            self.log.info(f"ELisA logbook: Sent message (ID{thread_id})")
            os.remove(sso['ssocookie']) 
