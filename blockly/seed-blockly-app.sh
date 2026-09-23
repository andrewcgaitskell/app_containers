#!/bin/sh
set -e
 
WEB_ROOT=/usr/share/nginx/html
DEFAULT_SITE=/opt/blockly-app-default
 
# If the web root has no index.html (first run on an empty volume),
# copy the built site into it. Otherwise leave the existing files alone.
if [ ! -f "$WEB_ROOT/index.html" ]; then
  cp -r "$DEFAULT_SITE/." "$WEB_ROOT/"
fi

