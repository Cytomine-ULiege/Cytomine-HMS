#!/bin/bash

bash /tmp/addHosts.sh

T=$(cat /app/config.cfg | grep WAITRESS_THREADS)
T=(${T//=/ })
T=${T[1]}

waitress-serve --threads=$T --call 'cytomine_hms:create_app'