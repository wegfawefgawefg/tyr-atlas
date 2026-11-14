#!/bin/sh
# Serve the Tyr Tank Atlas locally: http://127.0.0.1:8740/
cd "$(dirname "$0")/site" && exec python3 -m http.server 8740 --bind 127.0.0.1
