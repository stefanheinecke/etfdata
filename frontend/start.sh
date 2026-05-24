#!/bin/bash
set -e
exec serve -s dist -l ${PORT:-3000}
