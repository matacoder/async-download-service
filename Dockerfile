# syntax=docker/dockerfile:1

FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
	&& apt-get install -y zip \
	&& rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt


COPY . .

CMD [ "python3", "-m" , "server" ]