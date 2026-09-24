#!/bin/sh
# Update categor.io to the latest version on GitHub — see docs/DEPLOY.md.
# Install: cp deploy/update.sh /usr/local/bin/categorio-update
# Run:     sudo categorio-update
#
# Backs up the data first, pulls, reinstalls, restarts, and checks that the
# site answers. If it does not, it goes back to the previous version.
# The data folder is never touched: only the code changes.
set -eu

# Overridable only so the script can be tested in a sandbox.
APP=${CATEGORIO_APP:-/srv/categorio/app}
VENV=${CATEGORIO_VENV:-/srv/categorio/venv}
SITE=${CATEGORIO_SITE:-http://127.0.0.1:8000/}
UNIT=${CATEGORIO_UNIT:-/etc/systemd/system/categorio.service}
BACKUP=${CATEGORIO_BACKUP:-/usr/local/bin/categorio-backup}
WAIT=${CATEGORIO_WAIT:-30}
as_site() { sudo -u categorio "$@"; }

[ "$(id -u)" = 0 ] || { echo "Run it with sudo: sudo categorio-update"; exit 1; }

install_and_restart() {
    as_site "$VENV/bin/pip" install -q -e "$APP[serve]"
    # the service file travels with the code; keep the installed one in step
    if ! cmp -s "$APP/deploy/categorio.service" "$UNIT"; then
        echo "→ the service file changed; installing it"
        cp "$APP/deploy/categorio.service" "$UNIT"
        systemctl daemon-reload
    fi
    systemctl restart categorio
}

site_answers() {
    for _ in $(seq 1 "$WAIT"); do
        if curl -fsS -o /dev/null "$SITE"; then return 0; fi
        sleep 1
    done
    return 1
}

OLD=$(as_site git -C "$APP" rev-parse HEAD)
echo "→ fetching the latest version"
as_site git -C "$APP" fetch -q origin
NEW=$(as_site git -C "$APP" rev-parse origin/main)
if [ "$OLD" = "$NEW" ]; then
    echo "Already up to date ($(as_site git -C "$APP" log -1 --format='%h %s'))."
    exit 0
fi
echo "→ changes:"
as_site git -C "$APP" log --format='   %h %s' "$OLD..$NEW"

echo "→ backing up the data first"
STAMP="$(date +%F-%H%M%S)-before-update" "$BACKUP"

echo "→ updating the code"
as_site git -C "$APP" merge -q --ff-only "$NEW"
install_and_restart

echo "→ checking the site"
if site_answers; then
    echo "Updated: $(as_site git -C "$APP" log -1 --format='%h %s')"
else
    echo "!! The new version does not answer. Going back to $(echo "$OLD" | cut -c1-7)."
    journalctl -u categorio -n 30 --no-pager || true
    as_site git -C "$APP" reset -q --hard "$OLD"
    install_and_restart
    if site_answers; then
        echo "Back on the previous version; the site is running. Nothing in the data changed."
    else
        echo "!! The previous version does not answer either: sudo journalctl -u categorio -n 100"
    fi
    exit 1
fi

# The installed copy of this script is root's, not the repository's (running
# the site account's files as root would hand it root). Say when they differ.
if ! cmp -s "$APP/deploy/update.sh" "$0"; then
    echo "Note: a newer categorio-update came with this version. Install it with:"
    echo "  sudo cp $APP/deploy/update.sh /usr/local/bin/categorio-update"
fi
if ! cmp -s "$APP/deploy/backup.sh" "$BACKUP"; then
    echo "Note: a newer categorio-backup came with this version. Install it with:"
    echo "  sudo cp $APP/deploy/backup.sh /usr/local/bin/categorio-backup"
fi
