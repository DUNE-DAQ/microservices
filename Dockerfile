# Must define DEPENDENCY_TAG before it is used
ARG DEPENDENCY_TAG=latest
FROM ghcr.io/dune-daq/microservices_dependencies:${DEPENDENCY_TAG}

ARG MICROSERVICES_VERSION=develop

RUN cd ${APP_ROOT} \
  && git clone -b ${MICROSERVICES_VERSION} https://github.com/DUNE-DAQ/microservices.git \
  && cp entrypoint.sh /

WORKDIR ${APP_ROOT}/microservices

ENTRYPOINT ["/entrypoint.sh"]
