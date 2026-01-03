# Must define DEPENDENCY_TAG before it is used
ARG DEPENDENCY_TAG=latest
FROM ghcr.io/dune-daq/microservices_dependencies:$DEPENDENCY_TAG

ARG MICROSERVICES_VERSION=develop
RUN git clone -b ${MICROSERVICES_VERSION} https://github.com/DUNE-DAQ/microservices.git \
    && cp microservices/entrypoint.sh /

WORKDIR ${APP_ROOT}/microservices

USER 1234
ENTRYPOINT ["/entrypoint.sh"]
