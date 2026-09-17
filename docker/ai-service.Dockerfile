FROM python:3.10-slim

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin ereview

COPY ai-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

USER ereview

EXPOSE 8008
