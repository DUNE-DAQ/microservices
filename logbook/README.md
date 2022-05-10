# logbook-test
There are 6 different URLs that can be used, three for each kind of logbook. Examples of how to use each one with curl can be found in logbook.py, above their respective parts of the code.

<h2>File Logbook</h2>
/v1/fileLogbook/message_on_start/ is used to create a new file with a message. It accepts POST requests.<br />
/v1/fileLogbook/add_message/ is used to append messages to an existing file. It accepts PUT requests.<br />
/v1/fileLogbook/message_on_stop/ is used to add a final message to a file. It accepts PUT requests.<br />
All of these requests need the author, message, run_num and run_type variables to be provided.

<h2>ELisA Logbook</h2>
/v1/elisaLogbook/message_on_start/ is used to start a new message thread in ELisA, with a user supplied message. It accepts POST requests.<br />
/v1/elisaLogbook/add_message/ is used to add a message to the current thread in ELisA. It accepts PUT requests.<br />
/v1/elisaLogbook/message_on_stop/ is used to add a final message to the current thread in ELisA. It accepts PUT requests.<br />
message_on_start and message_on_stop need the author, message, run_num and run_type variables to be provided. add_message just needs the author and message.<br />
