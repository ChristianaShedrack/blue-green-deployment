#!/bin/sh

if [ "$ACTIVE_POOL" = "blue" ]; then
  export RELEASE_ID=$RELEASE_ID_BLUE
else
  export RELEASE_ID=$RELEASE_ID_GREEN
fi

envsubst '${PORT} ${ACTIVE_POOL} ${RELEASE_ID}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

nginx -g 'daemon off;'
