#!/bin/sh
set -e

if [ "$1" = 'call' ]; then
    exec python callbot.py
fi

if [ "$1" = 'serve' ]; then
    exec python callbot.py --serve
fi

if [ "$1" = 'check' ]; then
    exec python callbot.py --check
fi

exec "$@"
