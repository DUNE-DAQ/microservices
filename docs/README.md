# microservices

To run one of the provided microservices in this repo, the basic command is the following:
```
docker run --rm -e MICROSERVICE=<name of microservice> microservices:cc4f
```

There are a couple of points to note:
* The value of MICROSERVICE should be the name of a given microservice's subdirectory in this repo. As of Oct-6-2023, the available subdirectories are: `config-service`, `ers-dbwriter`, `logbook`, `opmon-dbwriter`, `runnumber-rest` and `runregistry-rest`. 
* Most microservices require additional environment variables to be set, which can be passed using the usual docker syntax: `-e VARIABLE_NAME=<variable value>`
* If you don't know what these additional environment variables are, you can just run the `docker` command as above without setting them; the container will exit out almost immediately but only after telling you what variables are missing
* The `cc4f` tag for the image in the example above just refers to the first four characters of the git commit of the microservices repo whose `dockerfiles/Dockerfile.microservices` Docker file was used to create the image

For details on a given microservice, look at its own README file (format is `README_<microservice name>.md`)
