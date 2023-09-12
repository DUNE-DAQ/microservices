FROM cern/alma9-base

RUN yum clean all \
  && yum -y install gcc make git libpq-devel libffi-devel  \
  && yum clean all

RUN yum -y install python3-pip python3-wheel

COPY requirements.txt /
RUN pip3 install --upgrade setuptools && pip3 install -r requirements.txt 

RUN yum -y install libaio libnsl  # Needed when rpm is called on the Oracle client software 

RUN curl -O https://download.oracle.com/otn_software/linux/instantclient/1919000/oracle-instantclient19.19-basic-19.19.0.0.0-1.el9.x86_64.rpm \
  && rpm -iv oracle-instantclient19.19-basic-19.19.0.0.0-1.el9.x86_64.rpm


 
