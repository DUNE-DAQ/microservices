FROM ghcr.io/dune-daq/c8-minimal:latest

RUN yum clean all \
 && yum -y install python3.11 python3.11-devel python3.11-pip python3.11-wheel \
 && yum clean all

RUN python3 -m pip install --upgrade pip

RUN yum clean all \
  && yum -y install gcc libpq-devel libffi-devel \
  && yum clean all

