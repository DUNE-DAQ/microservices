FROM dunedaq/c8-minimal

RUN yum clean all \
 && yum -y install python3-pip \
 && yum -y install python3-devel \
 && yum clean all

COPY archiver.py /
COPY checkoutConfig.py / 
COPY conf-service.py / 
COPY configconfig.py /
COPY mongoTest.py / 
COPY requirements.txt / 
COPY uploadConfig.py / 

RUN pip3 install --upgrade pip
RUN pip3 install -r /requirements.txt

COPY entrypoint.sh /
RUN ["chmod", "+x", "/entrypoint.sh"]
ENTRYPOINT ["/entrypoint.sh"]
