FROM tjongen/pbc25base:latest

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

ENTRYPOINT [ "python", "player.py" ]
