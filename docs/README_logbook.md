# logbook-test
<h2>Instructions for use</h2>
To run the service locally, clone the repository and do `python3 logbook.py`. Assuming this was done on one of the np04 servers, all of the relevant dependencies should already be present. Otherwise, ensure that Kerberos, Flask, and auth-get-sso-cookie are installed. Before running, the The USERNAME, PASSWORD and HARDWARE environment variables must be set. HARDWARE is either "npvd" or "pdsp", and determines which logbook website the messages will be sent to. Once the flask server is running, requests can be sent to it on port 5005. For production use, there are four instances running in the kubernetes cluster: two for each website, with production and development versions. `kubectl get all -n elisa-logbook` will show all relevant information, such as the port numbers for each service.
<h2>URL Documentation</h2>
There are 5 routes available in total. The first three will save logs locally as text files: this is legacy code from nanorc and will probably not be very useful for most users. The remaining two will send the logs to an ELisA logbook, for long-term storage. The routes are defined in `logbook.py` and have an example curl request for each one provided as a comment
<h3>File Logbook</h3>
/v1/fileLogbook/message_on_start/ is used to create a new file with a message. It accepts POST requests.<br />
/v1/fileLogbook/add_message/ is used to append messages to an existing file. It accepts PUT requests.<br />
/v1/fileLogbook/message_on_stop/ is used to add a final message to a file. It accepts PUT requests.<br />
All of these requests need the author, message, run_num and run_type variables to be provided.

<h3>ELisA Logbook</h3>
/v1/elisaLogbook/new_message/ is used to start a new message thread in ELisA, with a user supplied message. It accepts POST requests.<br />
/v1/elisaLogbook/reply_to_message/ is used to add a message to an existing thread in ELisA. It accepts PUT requests.<br />
Both of these routes require the author, body, command and systems variables to be provided in a JSON. title and ID must also be provided to `new_message` and `reply_to_message` respectively: the id can be obtained from the response when successfully posting a message.<br />
