# Must define DEPENDENCY_TAG before it is used, gets undefined after FROM
ARG DEPENDENCY_TAG=latest
FROM ghcr.io/dune-daq/microservices_dependencies:$DEPENDENCY_TAG

ARG MICROSERVICES_VERSION=develop

RUN echo "FROM ghcr.io/dune-daq/microservices_dependencies" \
    && git clone https://github.com/DUNE-DAQ/microservices.git \
    && cd microservices \
    && echo "https://github.com/DUNE-DAQ/microservices.git -> ${MICROSERVICES_VERSION}" \
    && git checkout ${MICROSERVICES_VERSION} \
    && : "${APP_ROOT:?APP_ROOT variable is required}" \
    && cp ./entrypoint.sh /

WORKDIR ${APP_ROOT}/microservices

USER 1234
ENTRYPOINT ["/entrypoint.sh"]
