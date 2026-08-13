#!/bin/sh

CONF="/opt/syncthing/.local/state/syncthing/config.xml"
HOST=10.100.0.1

# Default HOST if not set
: "${HOST:=127.0.0.1}"

# BusyBox sed uses -r for ERE (not -E)
sed -i -r \
  -e 's|(<autoUpgradeIntervalH>)[^<]*(</autoUpgradeIntervalH>)|\1\2|' \
  -e 's|(<releasesURL>)[^<]*(</releasesURL>)|\1\2|' \
  -e 's|(<crashReportingEnabled>)[^<]*(</crashReportingEnabled>)|\1false\2|' \
  -e "/<gui[^>]*>/,/<\/gui>/ s|(<address>)[^<]*(</address>)|\1${HOST}:8384\2|" \
  "$CONF"

