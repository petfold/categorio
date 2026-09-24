#!/bin/sh
# Nightly backup of categor.io's data — see docs/DEPLOY.md.
# Install: cp deploy/backup.sh /usr/local/bin/categorio-backup
set -eu
DATA=/srv/categorio/data
OUT=/var/backups/categorio
STAMP=$(date +%F)
umask 077
mkdir -p "$OUT"
# The logins database, copied safely while the site runs.
sqlite3 "$DATA/logins.sqlite" ".backup '$OUT/logins-$STAMP.sqlite'"
# Every account's store (content-addressed files: new ones are only added).
tar -C "$DATA" -czf "$OUT/stores-$STAMP.tar.gz" stores
# Keep two weeks.
find "$OUT" -type f -mtime +14 -delete
