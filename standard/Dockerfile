FROM cern/alma9-base

RUN yum clean all \
  && yum -y install gcc libpq-devel libffi-devel \
  && yum clean all

RUN yum -y install python3-pip python3-wheel

COPY requirements.txt /
RUN pip3 install -r requirements.txt
