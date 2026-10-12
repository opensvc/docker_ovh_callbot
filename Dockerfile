FROM python:3.13-alpine

LABEL org.opencontainers.image.source="https://github.com/opensvc/docker_ovh_callbot"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY callbot.py server.py ./

COPY docker-entrypoint.sh /

RUN chmod +x /docker-entrypoint.sh

USER nobody

EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]

CMD ["call"]
