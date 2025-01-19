FROM tjongen/pbc25base:latest

WORKDIR /app
COPY . /app

RUN ["dos2unix", "build.sh", "run.sh"]
RUN ["bash", "build.sh"]

RUN chmod +x ./run.sh
ENTRYPOINT [ "./run.sh" ]
