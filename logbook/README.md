# logbook-test
<h2>Instructions for use</h2>
To run the API outside of a container, it is recommended to git clone into your user area on lxplus, in order to skip the installation of kerberos, the ELisA client and some perl modules. No arguments are given: the API gets the data needed for initialisation from three environment variables(USERNAME, PASSWORD and HARDWARE). Remember to set these before you run. To run in a container, use docker build to create an image from the dockerfile, and docker run to make the container. Environment variables should be set using the -e flag. The final method (arguably the best) is to just use the instance already running on the np04-srv-015 kubernetes cluster. In this case, localhost must be replaced with the cluster ip in all URLs.
  
<h2>URL Documentation</h2>
There are 6 different URLs that can be used, three for each kind of logbook. Examples of how to use each one with curl can be found as comments inside of logbook.py, above their respective parts of the code.

<h3>File Logbook</h3>
/v1/fileLogbook/message_on_start/ is used to create a new file with a message. It accepts POST requests.<br />
/v1/fileLogbook/add_message/ is used to append messages to an existing file. It accepts PUT requests.<br />
/v1/fileLogbook/message_on_stop/ is used to add a final message to a file. It accepts PUT requests.<br />
All of these requests need the author, message, run_num and run_type variables to be provided.

<h3>ELisA Logbook</h3>
/v1/elisaLogbook/message_on_start/ is used to start a new message thread in ELisA, with a user supplied message. It accepts POST requests.<br />
/v1/elisaLogbook/add_message/ is used to add a message to the current thread in ELisA. It accepts PUT requests.<br />
/v1/elisaLogbook/message_on_stop/ is used to add a final message to the current thread in ELisA. It accepts PUT requests.<br />
message_on_start and message_on_stop need the author, message, run_num and run_type variables to be provided. add_message just needs the author and message.<br />
