FROM python:3-alpine

WORKDIR /opt

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY callbot.py .

COPY ./docker-entrypoint.sh /

RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]

CMD ["call"]
