# syntax=docker/dockerfile:1

FROM python:3.8-slim

RUN apt-get update -y \
	&& apt-get install -y zip

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt


COPY . .

CMD [ "python3", "-m" , "server" ]