#!/bin/sh

ENV_FILE=/opt/c2ptt/normhosts.env

if [ -f "$ENV_FILE" ]; then
    . "$ENV_FILE"
else
    echo "Missing env file: $ENV_FILE" >&2
    exit 1
fi

FILE="$1"

if [ -z "$FILE" ]; then
    echo "No filename given" >&2
    exit 1
fi

if [ ! -f "$FILE" ]; then
    echo "Not a regular file: $FILE" >&2
    exit 1
fi

if [ -z "$NORM_REMOTE" ]; then
    echo "NORM_REMOTE is not set" >&2
    exit 1
fi

echo "Processing file: $FILE"

spacecom-send addr "${NORM_REMOTE}/6003" "$FILE"

rm -f -- "$FILE"
