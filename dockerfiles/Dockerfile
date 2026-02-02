# Must define DEPENDENCY_TAG before it is used
ARG DEPENDENCY_TAG=latest
FROM ghcr.io/dune-daq/microservices_dependencies:$DEPENDENCY_TAG

ARG MICROSERVICES_VERSION=develop
RUN : "${APP_ROOT:?APP_ROOT variable is required}" \
    && git clone https://github.com/DUNE-DAQ/microservices.git \
    && cd microservices \
    && git checkout ${MICROSERVICES_VERSION} \
    && cp ./entrypoint.sh /

WORKDIR ${APP_ROOT}/microservices

USER 1234
ENTRYPOINT ["/entrypoint.sh"]
