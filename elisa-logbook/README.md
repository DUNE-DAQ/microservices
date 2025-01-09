# Elisa Logbook Microservice
## To test the microservice
On a machine at CERN:
 - Clone the repository `git clone https://github.com/DUNE-DAQ/microservices.git`
 - Clone the repository `git clone https://github.com/DUNE-DAQ/elisa_client_api.git`
 - Create a virtual environment `python3 -m venv .venv`
 - Activate the virtual environment `source .venv/bin/activate`
 - Install the dependencies `pip install -r microservices/dockerfiles/requirements.txt`
 - Install the elisa_client_api `pip install ./elisa_client_api`
 - `cd` into this directory: `cd microservices/elisa-logbook`
 - Run `pytest`
 - Once done, deactivate the virtual environment: `deactivate`

If you don't want to be spamming ELisA logbook, you can run only one test for example:
```bash
python -m pytest -k test_elisa_microservice_conf
```
or choose a specific system:
```bash
python -m pytest --system pddp -k test_elisa_microservice_locally
```
