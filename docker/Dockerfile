FROM python:3.9

ENV FLASK_APP "cytomine_hms"
ENV FLASK_ENV "production"
ENV FLASK_DEBUG False
ENV CONFIG_FILE "/app/config.cfg"

RUN apt-get update && apt-get install -y net-tools gawk

RUN mkdir /app
WORKDIR /app

# Install python requirements
ARG WAITRESS_VERSION=2.1.0
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir WAITRESS==${WAITRESS_VERSION} && \
    pip install --no-cache-dir -r requirements.txt

# Prestart configuration
RUN touch /tmp/addHosts.sh
COPY ./docker/prestart.sh /app/prestart.sh
RUN chmod +x /app/prestart.sh
COPY ./docker/start.sh /start.sh
RUN chmod +x /start.sh

# Add default config
COPY ./config.cfg /app/config.cfg

# Add app
COPY ./cytomine_hms /app/cytomine_hms

ENV PORT=8080
EXPOSE ${PORT}

ENTRYPOINT ["/start.sh"]