#!/bin/bash

SCRIPT_PATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
VERSION=$(cd $SCRIPT_PATH && cd .. && python -c "from cytomine_hms import __version__; print(__version__)")
TAG="v${VERSION}"
NAMESPACE=cytomineuliege

docker build -f ../docker/Dockerfile \
  -t ${NAMESPACE}/hms:${TAG} \
  ..
