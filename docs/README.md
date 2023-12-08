# microservices

To run one of the provided microservices in this repo, the basic command is the following:
```
docker run --rm -e MICROSERVICE=<name of microservice> ghcr.io/dune-daq/microservices:9685
```

There are a couple of points to note:
* The value of MICROSERVICE should be the name of a given microservice's subdirectory in this repo. As of Oct-6-2023, the available subdirectories are: `config-service`, `ers-dbwriter`, `ers-protobuf-dbwriter`, `logbook`, `opmon-dbwriter`, `runnumber-rest` and `runregistry-rest`. 
* Most microservices require additional environment variables to be set, which can be passed using the usual docker syntax: `-e VARIABLE_NAME=<variable value>`
* If you don't know what these additional environment variables are, you can just run the `docker` command as above without setting them; the container will exit out almost immediately but only after telling you what variables are missing
* The `9685` tag for the image in the example above just refers to the first four characters of the git commit of the microservices repo whose `dockerfiles/Dockerfile.microservices` Docker file was used to create the image. Currently [Dec-08-2023] this is the head of a branch soon to be merged in develop with a PR. 

For details on a given microservice, look at its own README file (format is `docs/README_<microservice name>.md`). They may or may not be up to date, however.

## building images
When building from a branch that is not develop you need to specify the branch you want to use to build the code, e.g.:
```bash
docker build -f Dockerfile.microservices -t ghcr.io/dune-daq/microservices:user-my-branch --build-arg BRANCH=my-branch .
```
