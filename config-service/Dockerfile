FROM ghcr.io/dune-daq/c8-minimal:latest

EXPOSE 5003

RUN yum clean all \
 && yum -y install python3 python3-pip python3-wheel \
 && yum clean all

COPY conf-service.py  configconfig.py requirements.txt / 

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r /requirements.txt

COPY --chmod=755 entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
