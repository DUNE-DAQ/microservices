FROM docker.io/almalinux:9

ARG ERSVERSION=v1.5.2  # For issue.proto from ers
ARG ERSKAFKAVERSION=v1.5.4  # For ERSSubscriber.py from erskafka
ARG OPMONLIBVERSION=v2.0.0  # For opmon_entry.proto from opmonlib
ARG KAFKAOPMONVERSION=v2.0.0  # For OpMonSubscriber.py from kafkaopmon

ARG VENV_PATH=/opt/venv
ENV \
    APP_ROOT=/opt/app        \
    APP_DATA=/opt/data       \
    HOME=/opt/app            \
    PYTHONUNBUFFERED=1       \
    PIP_NO_CACHE_DIR=1

ENV PATH="${VENV_PATH}/bin:$PATH"

RUN mkdir -p ${APP_ROOT} ${APP_DATA} ${VENV_PATH}
WORKDIR ${APP_ROOT}

RUN yum clean expire-cache \
    && yum -y install gcc make git libpq-devel libffi-devel python3-pip python3-pip-wheel krb5-devel python3-devel \
    && yum clean all

# setup venv
RUN python3 -m venv ${VENV_PATH}

COPY requirements.txt ${VENV_PATH}/
RUN ${VENV_PATH}/bin/pip install --no-cache-dir -r ${VENV_PATH}/requirements.txt \
    && rm -rf /root/.cache ${HOME}/.cache ${VENV_PATH}/pip-selfcheck.json

COPY cern.repo /etc/yum.repos.d/
RUN yum clean expire-cache \
    && yum -y install krb5-workstation cern-krb5-conf \
    && yum clean all

# elisa_client_api needed by the logbook microservice
RUN git clone https://github.com/DUNE-DAQ/elisa_client_api.git \
    && ${VENV_PATH}/bin/pip install --no-cache-dir ./elisa_client_api \
    && rm -rf /root/.cache ${HOME}/.cache ${VENV_PATH}/pip-selfcheck.json

# protoc-24.3-linux-x86_64.zip is the latest zipfile available as of Sep-15-2023
# See also https://grpc.io/docs/protoc-installation/#install-pre-compiled-binaries-any-os

RUN yum clean expire-cache \
    && yum -y install unzip \
    && yum clean all \
    curl -LO https://github.com/protocolbuffers/protobuf/releases/download/v24.3/protoc-24.3-linux-x86_64.zip \
    && unzip protoc-24.3-linux-x86_64.zip \
    && curl -O https://raw.githubusercontent.com/DUNE-DAQ/ers/${ERSVERSION}/schema/ers/issue.proto \
    && mkdir -p ${VENV_PATH}/ers \
    && protoc --python_out=${VENV_PATH}/ers issue.proto \
    && curl -O https://raw.githubusercontent.com/DUNE-DAQ/opmonlib/${OPMONLIBVERSION}/schema/opmonlib/opmon_entry.proto \
    && mkdir -p ${VENV_PATH}/opmonlib \
    && protoc --python_out=${VENV_PATH}/opmonlib -I/ -I/include opmon_entry.proto

RUN mkdir -p ${VENV_PATH}/erskafka \
    && curl https://raw.githubusercontent.com/DUNE-DAQ/erskafka/${ERSKAFKAVERSION}/python/erskafka/ERSSubscriber.py -o ${VENV_PATH}/erskafka/ERSSubscriber.py \
    && mkdir -p ${VENV_PATH}/kafkaopmon \
    && curl https://raw.githubusercontent.com/DUNE-DAQ/kafkaopmon/${KAFKAOPMONVERSION}/python/kafkaopmon/OpMonSubscriber.py -o ${VENV_PATH}/kafkaopmon/OpMonSubscriber.py
