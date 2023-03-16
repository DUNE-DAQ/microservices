FROM docker.io/almalinux:9

RUN yum clean all \
 && yum -y install python3-pip python3-devel git \
 && yum clean all


RUN git clone --depth 1 -b v1.0.0 https://github.com/DUNE-DAQ/connectivityserver.git
RUN pip3 install /connectivityserver

COPY entrypoint.sh /
RUN ["chmod", "+x", "/entrypoint.sh"]
ENTRYPOINT ["/entrypoint.sh"]
