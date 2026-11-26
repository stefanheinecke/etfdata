#!/bin/sh
set -eu

node /app/write-runtime-config.cjs
exec serve -s /app/dist -l "${PORT:-3000}"
