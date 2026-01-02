# microservices

To run one of the provided microservices in this repo, the basic command is the following:
```
docker run --rm -e MICROSERVICE=<name of microservice> ghcr.io/dune-daq/microservices:develop
```

There are a couple of points to note:
* The value of MICROSERVICE should be the name of a given microservice's subdirectory in this repo. As of Jul-25-2024, the available subdirectories are: `config-service`, `elisa-logbook`, `ers-dbwriter`, `ers-protobuf-dbwriter`, `opmon-dbwriter` (now deprecated), `opmon-protobuf-dbwriter`, `runnumber-rest` and `runregistry-rest`.
* Most microservices require additional environment variables to be set, which can be passed using the usual docker syntax: `-e VARIABLE_NAME=<variable value>`
* If you don't know what these additional environment variables are, you can just run the `docker` command as above without setting them; the container will exit out almost immediately but only after telling you what variables are missing
* The microservices image tag will be `microservices:<name-of-branch>` or `microservices:<version-tag>`, i.e. `microservices:develop`.
* The microservices dependency image tag is `microservices_dependencies:<name-of-branch>` or `microservices_dependencies:<version-tag>`

For details on a given microservice, look at its own README file (format is `docs/README_<microservice name>.md`). They may or may not be up to date, however.

## Building images
There are two workflow actions on GitHub to build the `microservices` and `microservices_dependencies` images. This can be run on GitHub directly and will create the images, tag them and push them for use.

The `microservices_dependencies` image is used as the base image for `microservies` and so any changes to the `requirements.txt` file requires rebuilding the `microservices_dependencies` image.

If you do not wish to to push your changes to the repo when testing, you can also use:

```bash
docker build -f dockerfiles/Dockerfile -t ghcr.io/dune-daq/microservices:user-my-branch .

docker push ghcr.io/dune-daq/microservices:user-my-branch
```
and

```bash
docker build -f dockerfiles/Dockerfile.dependencies -t ghcr.io/dune-daq/microservices_dependencies:user-my-branch /dockerfiles

docker push ghcr.io/dune-daq/microservices_dependencies:user-my-branch
```

This will copy your current microservices directory for the dependencies.
