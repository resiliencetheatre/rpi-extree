#!/usr/bin/env bash
#
# Update all defconfig's with new kernel commit ID.
#
# Take latest commit id from RPi kernel repository:
#
# https://github.com/raspberrypi/linux.git
#
# Remember to do full clean build after this change!
#
# Usage:
#   ./update_defconfig_commit.sh NEW_COMMIT_ID
#

set -e

if [ $# -ne 1 ]; then
  echo "Usage: $0 <new_commit_id>"
  exit 1
fi

NEW_COMMIT_ID="$1"

# Iterate over *_defconfig files in configs/
for file in configs/*_defconfig; do
  if [ -f "$file" ]; then
    echo "Updating $file..."
    # Use sed to replace both occurrences of the commit ID
    sed -i -E \
      "s|(github,[^,]+,[^,]+,)[a-f0-9]+|\1${NEW_COMMIT_ID}|; s|(linux-)[a-f0-9]+(\.tar\.gz)|\1${NEW_COMMIT_ID}\2|" \
      "$file"
  fi
done

echo "All defconfig files updated successfully."
