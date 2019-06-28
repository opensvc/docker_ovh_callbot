#!/bin/sh
set -e

if [ "$1" = 'call' ]; then
    exec python callbot.py
fi

exec "$@"
