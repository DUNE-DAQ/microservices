ARG DEPENDENCY_TAG=latest
FROM ghcr.io/dune-daq/microservices_dependencies:$DEPENDENCY_TAG

COPY . /microservices

ENTRYPOINT ["/microservices/entrypoint.sh"]