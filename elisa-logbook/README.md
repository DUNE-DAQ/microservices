# Elisa Logbook Microservice
## To test the microservice
On a machine at CERN:
```bash
git clone https://github.com/DUNE-DAQ/microservices.git #  Clone this repository
git clone https://github.com/DUNE-DAQ/elisa_client_api.git #  Clone the elisa_client_api repository
python3 -m venv .venv #  Create a virtual environment
source .venv/bin/activate #  Activate the virtual environment
pip install -r microservices/dockerfiles/requirements.txt #  Install the dependencies
pip install ./elisa_client_api #  Install the elisa_client_api
pip install pytest #  Install pytest
cd microservices/elisa-logbook
USERNAME=something PASSWORD=something python -m pytest -s --system pdsp -k test_elisa_microservice_locally
# After running the tests:
deactivate
```
You need to provide the service account username and password for the ELisA logbook. Ask Pierre Lasorak for the credentials.


If you don't want to be spamming the ELisA logbook too much, you can run a subset of tests for example:
```bash
python -m pytest -k test_elisa_microservice_conf
```
or choose a specific system:
```bash
python -m pytest --system pddp -k test_elisa_microservice_locally
```
