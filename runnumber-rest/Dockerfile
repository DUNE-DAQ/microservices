FROM cern/cc7-base

RUN yum clean all \
 && yum -y install python3-pip \
 && yum -y install python3-devel \
 && yum --enablerepo=cernonly -y install oracle-instantclient12.1-devel \
 && yum --enablerepo=cernonly -y install oracle-instantclient-tnsnames.ora \
 && yum clean all

COPY authentication.py credentials.py rest.py backend.py queries.py requirements.txt /

RUN python3 -m pip install --upgrade pip && python3 -m pip install -r /requirements.txt && pip cache remove *

COPY --chmod=755 entrypoint.sh /

USER 10000:0
ENV LD_LIBRARY_PATH=/usr/lib/oracle/12.1/client64/lib/
ENTRYPOINT ["/entrypoint.sh"]
