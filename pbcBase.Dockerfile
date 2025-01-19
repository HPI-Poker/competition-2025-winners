# You DON'T need to build the image yourself if you are using an x86 or ARM architecture. 
# If you have a different architecture, you need to build the base image yourself by running: 
# `docker build -t tjongen/pbc25base -f pbcBase.Dockerfile .`.

FROM python:3.8

RUN apt-get update && \
    apt-get upgrade -y;

# Install C++ and other dependencies
RUN apt-get install -y build-essential cmake libboost-all-dev libfmt-dev clang dos2unix;

# Install dependencies specified in the environment.yml file. Need to seperate in two steps to avoid errors!
RUN pip install cython==3.0.11 python-dotenv==1.0.1
RUN pip install eval7==0.1.10

ENV CC=/usr/bin/clang
ENV CXX=/usr/bin/clang++
