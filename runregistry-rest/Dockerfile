# this should move to github container registry at some point
# and should probably be based on one of our baseline containers
FROM docker.io/dunedaq/pocket-runregistry-rest:0.2

#RUN yum clean all \
# && yum -y install python3-devel \
# && yum -y install python3-pip \
# && yum -y install python3-wheel \
# && yum --enablerepo=cernonly -y install oracle-instantclient12.1-devel \
# && yum --enablerepo=cernonly -y install oracle-instantclient-tnsnames.ora \
# && yum clean all

# ENV LD_LIBRARY_PATH=/usr/lib/oracle/12.1/client64/lib/

COPY authentication.py credentials.py rest.py requirements.txt /
COPY ./backends/. /backends/

RUN mkdir --mode=1777 /uploads

RUN pip3 install --upgrade pip
RUN pip3 install -r /requirements.txt

COPY --chmod=755 entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
