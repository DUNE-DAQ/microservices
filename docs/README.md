# microservices

To run one of the provided microservices, `cd` into any of the following subdirectories of this repo:
```
./config-service
./ers-dbwriter
./logbook
./opmon-dbwriter
./runnumber-rest
./runregistry-rest
```
and then use `docker` to volume bind to that subdirectory and launch a container using that subdirectory's `entrypoint.sh` script, i.e.:
```
docker run --rm -v$PWD:/basedir -w /basedir --entrypoint ./entrypoint.sh ghcr.io/dune-daq/microservices:989e
```
...where `basedir` is an arbitrary choice for the name of the subdirectory _inside_ the container, and depending on the microservice you may also be required to pass one or more environment variables to the container (via the `-e` argument, i.e. `-e NAME_OF_ENV_VAR=<value of env var>`)

For details on a given microservice, look at its own README file (format is `README_<microservice name>.md`)
