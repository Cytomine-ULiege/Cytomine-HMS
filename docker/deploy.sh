#!/bin/bash

bash /tmp/addHosts.sh

waitress-serve --call 'cytomine_hms:create_app'