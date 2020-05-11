FROM python:3.6

ENV FLASK_APP "cytomine_hms"
ENV FLASK_ENV "production"
ENV FLASK_DEBUG False
ENV CONFIG_FILE "/app/config.cfg"

RUN apt-get update && apt-get install -y net-tools gawk
RUN mkdir /app
WORKDIR /app
COPY cytomine_hms /app/cytomine_hms
COPY setup.py /app

RUN curl -s https://packagecloud.io/install/repositories/cytomine-uliege/Cytomine-python-client/script.python.sh | bash
RUN pip install /app && pip install waitress

COPY docker/deploy.sh /app/deploy.sh
RUN chmod +x /app/deploy.sh

ENTRYPOINT ["/app/deploy.sh"]