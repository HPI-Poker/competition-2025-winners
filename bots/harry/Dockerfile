FROM tjongen/pbc25base:latest

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app

ENTRYPOINT [ "python", "player.py" ]
