FROM cern/cc7-base

RUN yum -y install python3-pip python3-devel libpq-devel gcc \
 && yum clean all

COPY requirements.txt /
COPY dbwriter.py /
COPY entrypoint.sh /

RUN pip3 install -r requirements.txt

ENTRYPOINT ["/entrypoint.sh"]
