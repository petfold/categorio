#!/bin/sh
# Nightly backup of categor.io's data — see docs/DEPLOY.md.
# Install: cp deploy/backup.sh /usr/local/bin/categorio-backup
set -eu
DATA=${CATEGORIO_DATA:-/srv/categorio/data}
OUT=${CATEGORIO_BACKUPS:-/var/backups/categorio}
# Members of this group may read the backups, to copy them off the server
# (docs/ADMIN.md). Without the group, only root can.
GROUP=${CATEGORIO_BACKUP_GROUP:-categorio-backups}
STAMP=${STAMP:-$(date +%F)}         # categorio-update passes its own
umask 077
mkdir -p "$OUT"
# The logins database, copied safely while the site runs.
sqlite3 "$DATA/logins.sqlite" ".backup '$OUT/logins-$STAMP.sqlite'"
# Every account's store (content-addressed files: new ones are only added).
tar -C "$DATA" -czf "$OUT/stores-$STAMP.tar.gz" stores
# Keep two weeks.
find "$OUT" -type f -mtime +14 -delete
if getent group "$GROUP" >/dev/null; then
    chgrp -R "$GROUP" "$OUT"
    chmod 750 "$OUT"
    chmod 640 "$OUT"/*
fi
