#! /usr/bin/env sh
set -e

T=$(cat /app/config.cfg | grep WAITRESS_THREADS)
T=(${T//=/ })
T=${T[1]}

# If there's a prestart.sh script in the /app directory or other path specified, run it before starting
PRE_START_PATH=${PRE_START_PATH:-/app/prestart.sh}
echo "Checking for script in $PRE_START_PATH"
if [ -f $PRE_START_PATH ] ; then
    echo "Running script $PRE_START_PATH"
    . "$PRE_START_PATH"
else
    echo "There is no script $PRE_START_PATH"
fi

waitress-serve --threads=$T --call 'cytomine_hms:create_app'
