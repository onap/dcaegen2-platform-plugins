FROM centos/python-27-centos7:latest as cent

# if needed set proxy
#ENV HTTP_PROXY=
#ENV HTTPS_PROXY=

RUN bash -c "pip install --upgrade pip"
RUN bash -c "pip install wagon"

COPY / k8s/

USER root
RUN bash -c "wagon create -r k8s/requirements.txt k8s/"
RUN bash -c "mkdir output"
RUN bash -c "mv k8splugin*.wgn output/"
