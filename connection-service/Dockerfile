FROM docker.io/dunedaq/c8-minimal:latest

RUN yum clean all \
 && yum -y install python3-pip \
 && yum -y install python3-devel \
 && yum clean all

COPY connection-flask.py /
COPY requirements.txt /

RUN pip3 install --upgrade pip
RUN pip3 install -r /requirements.txt

COPY entrypoint.sh /
RUN ["chmod", "+x", "/entrypoint.sh"]
ENTRYPOINT ["/entrypoint.sh"]
