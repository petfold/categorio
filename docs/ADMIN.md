# Running categor.io

The admin guide for the live site: how it is set up, and the everyday
tasks: updating, checking, backups, restoring, certificates, DNS and
accounts. Building a server from scratch is in [DEPLOY.md](DEPLOY.md).

This repository is public, so nothing secret is written here: no
passwords, no keys, no secret settings.

## At a glance

| What | Where |
|---|---|
| The site | https://categor.io (and www), on a Contabo VPS at 158.220.117.131, Ubuntu 24.04 |
| Logging in | `ssh peter@categor.io` — SSH keys only |
| Deploying a new version | `ssh -t peter@categor.io sudo categorio-update` |
| The code | `/srv/categorio/app` (a clone of github.com/petfold/categorio) |
| The data | `/srv/categorio/data` — logins and every account's store |
| Settings | `/etc/categorio.env` |
| Backups | `/var/backups/categorio`, nightly at 03:30, two weeks kept |
| The service | `categorio` (gunicorn on 127.0.0.1:8000), behind nginx |
| HTTPS | Let's Encrypt, renewed automatically |
| Domain | registered at Namecheap, DNS at Namecheap |

## Logging in

```bash
ssh peter@categor.io
```

- **The first time you use the name** (rather than the IP address), SSH
  asks "Are you sure you want to continue connecting?". It is the same
  server; answer `yes`.
- **Only SSH keys work.** Password login and root login are switched off.
  The keys allowed are in `/home/peter/.ssh/authorized_keys`.
- **`sudo` asks for `peter`'s password.** Keep it in a password manager.
- **If you lose every key,** the way back in is Contabo's web console (the
  VPS's "VNC" or rescue system) in the Contabo control panel. Keep that
  account safe too.

## Deploying a new version

From your own computer:

```bash
ssh -t peter@categor.io sudo categorio-update
```

The updater (`/usr/local/bin/categorio-update`):

1. fetches the latest version from GitHub and shows what changed. With
   nothing new it says "Already up to date" and stops.
2. backs up the data (`…-before-update` files in `/var/backups/categorio`);
3. installs the new code and restarts the site;
4. checks that the site answers. **If it does not, it prints the error and
   goes back to the previous version by itself.**

**User data and registrations are kept.** An update changes only
`/srv/categorio/app`; the data folder is never touched. Sessions survive
too, so people stay signed in. Lost on a restart: the console's recent
transcript, and an import preview waiting for "Merge".

**When the updater says a newer `update.sh` or `backup.sh` came with the
version,** install it with the `cp` command it prints. The installed copies
belong to root on purpose; see DEPLOY.md.

## Is it healthy?

As `peter`:

| Question | Command | Good answer |
|---|---|---|
| Is the site running? | `sudo systemctl status categorio --no-pager` | `active (running)` |
| Does it answer? | `curl -sI http://127.0.0.1:8000/ \| head -1` | `HTTP/1.1 200 OK` |
| Is nginx running? | `sudo systemctl status nginx --no-pager` | `active (running)` |
| The site's recent log | `sudo journalctl -u categorio -n 100 --no-pager` | requests, no tracebacks |
| nginx errors | `sudo tail -n 50 /var/log/nginx/error.log` | nothing recent |
| Disk space | `df -h /` | plenty free |
| Memory | `free -h` | the site uses about 60–100 MB |
| What's listening | `sudo ss -ltnp \| grep -E ':80\|:443\|:8000\|:22'` | nginx on 80/443, gunicorn on 127.0.0.1:8000, sshd on 22 |

From anywhere: open https://categor.io.

## Restart, stop, start

```bash
sudo systemctl restart categorio      # after changing /etc/categorio.env
sudo systemctl stop categorio
sudo systemctl start categorio
sudo systemctl reload nginx           # after changing nginx settings (check first: sudo nginx -t)
```

## Backups

- **Nightly** at 03:30 (`/etc/cron.d/categorio-backup` runs
  `/usr/local/bin/categorio-backup`): `logins-DATE.sqlite` and
  `stores-DATE.tar.gz` in `/var/backups/categorio`, kept for two weeks.
- **Before every update**, the updater makes a `…-before-update` pair.
- **By hand, at any time:** `sudo categorio-backup`.

These copies are on the same server. They protect against mistakes, not
against losing the server. **Copy them off the machine regularly.**

### Copying backups to your own computer

Once, on the server, let `peter` read the backups:

```bash
sudo groupadd categorio-backups
sudo usermod -aG categorio-backups peter
sudo categorio-backup                 # re-marks the files for the group
```

Log out and in again, for the new group to apply. Then, on your own
computer, whenever you like:

```bash
rsync -av peter@categor.io:/var/backups/categorio/ ~/categorio-backups/
```

The backup script re-marks each night's files for the group, so this keeps
working. The files hold password *hashes* (never passwords), but treat them
as private.

## Restoring a backup

Tested on a real backup: logins, stores and each store's history come back
intact.

1. Choose the date:
   ```bash
   sudo ls -l /var/backups/categorio
   ```
   Say you pick `2026-09-24`: the pair is `logins-2026-09-24.sqlite` and
   `stores-2026-09-24.tar.gz` (or the `…-before-update` pair).
2. Stop the site:
   ```bash
   sudo systemctl stop categorio
   ```
3. Set the current data aside (nothing is deleted):
   ```bash
   sudo mv /srv/categorio/data /srv/categorio/data-set-aside-$(date +%F-%H%M)
   ```
4. Put the backup in its place:
   ```bash
   sudo install -d -m 750 -o categorio -g categorio /srv/categorio/data
   sudo cp /var/backups/categorio/logins-2026-09-24.sqlite /srv/categorio/data/logins.sqlite
   sudo tar -C /srv/categorio/data -xzf /var/backups/categorio/stores-2026-09-24.tar.gz
   sudo chown -R categorio:categorio /srv/categorio/data
   ```
5. Start the site, and check:
   ```bash
   sudo systemctl start categorio
   curl -sI http://127.0.0.1:8000/ | head -1
   ```

Everything since that backup is lost from the live site, but it is still in
the set-aside folder. Remove that folder only when you are sure:
`sudo rm -r /srv/categorio/data-set-aside-…`.

## Going back to an earlier version of the code

The updater does this by itself when a new version fails to start. By
hand, as `peter`:

```bash
sudo -u categorio git -C /srv/categorio/app log --oneline -10   # pick a commit
sudo -u categorio git -C /srv/categorio/app reset --hard COMMIT
sudo -u categorio /srv/categorio/venv/bin/pip install -e "/srv/categorio/app[serve]"
sudo systemctl restart categorio
```

The next `categorio-update` moves forward to the latest version again.

## HTTPS certificate

- From Let's Encrypt, for `categor.io` and `www.categor.io`. It renews by
  itself (the `certbot` timer) well before it expires.
- **Check renewal:** `sudo certbot renew --dry-run`, which must end with
  "Congratulations, all simulated renewals succeeded".
- **See the dates:** `sudo certbot certificates`.
- Expiry warnings go to the email address given to certbot.

## Domain and DNS (Namecheap)

- `categor.io` is registered at **Namecheap**, which also serves its DNS
  ("Namecheap BasicDNS"). It expires on 22 October 2027; **keep
  auto-renew on** (Domain List → the domain).
- The records, in Namecheap → Domain List → Manage → **Advanced DNS**:

  | Type | Host | Value |
  |---|---|---|
  | A Record | `@` | 158.220.117.131 |
  | A Record | `www` | 158.220.117.131 |

  Leave the TXT record `v=spf1 include:spf.efwd.registrar-servers.com ~all`
  alone: it belongs to Namecheap's email forwarding.
- **If the server's address ever changes,** update both A records, then
  run `sudo certbot renew --dry-run` once the new address answers
  (`dig +short categor.io`).

## Accounts on the server

| Account | For | Rights |
|---|---|---|
| `peter` | the administrator | `sudo`, with its password; logs in with SSH keys |
| `claude` | a Claude Code instance on the server | no general `sudo`; only what `/etc/sudoers.d/claude-categorio` allows (below) |
| `categorio` | runs the site | owns `/srv/categorio`; can write only `/srv/categorio/data` while running; no login |
| `root` | — | no SSH login |

**Using the `claude` account:** log in as `peter`, then `sudo -iu claude`.
Its allowed commands, from `/etc/sudoers.d/claude-categorio`:

```
claude ALL=(root) NOPASSWD: /usr/bin/systemctl restart categorio, /usr/bin/systemctl status categorio, /usr/bin/journalctl -u categorio -n 200 --no-pager
claude ALL=(categorio) NOPASSWD: /usr/bin/git -C /srv/categorio/app pull, /srv/categorio/venv/bin/pip install -e /srv/categorio/app
```

To let it deploy with the updater as well (safe: it installs only what is
on GitHub, backs up first and rolls back on failure):

```bash
echo 'claude ALL=(root) NOPASSWD: /usr/local/bin/categorio-update' | sudo tee -a /etc/sudoers.d/claude-categorio
sudo visudo -c                        # must say: parsed OK
```

**Always run `sudo visudo -c` after touching a sudoers file.** A broken one
can stop `sudo` for everyone.

`claude` cannot read the site's data or its settings: they belong to
`categorio` and root.

## Adding or removing an SSH key

A key pair is a private half on your device and a public half on the
server. To allow a new device (a second laptop, say):

1. On that device: `ssh-keygen -t ed25519` (accept the defaults), then
   show its public half: `cat ~/.ssh/id_ed25519.pub`.
2. On the server, as `peter`, add that one line:
   ```bash
   echo 'ssh-ed25519 AAAA… name@device' >> ~/.ssh/authorized_keys
   ```
3. Test from the new device: `ssh peter@categor.io`.

To remove a key, delete its line from `~/.ssh/authorized_keys` with
`nano ~/.ssh/authorized_keys`. **Keep at least one working key**,
and test a login in a second window before closing the first.

## Security settings in place

- **SSH:** `/etc/ssh/sshd_config.d/00-hardening.conf` switches off root
  login and passwords. It is named `00-…` because sshd uses the first value
  it reads, and Ubuntu's `50-cloud-init.conf` would allow passwords. Check:
  `sudo sshd -T | grep -E '^(permitrootlogin|passwordauthentication) '`
  must print `no` twice.
- **Firewall:** `sudo ufw status` shows only OpenSSH and Nginx Full (80,
  443) allowed.
- **The service** runs unprivileged and sandboxed
  (`deploy/categorio.service`: it can write only its data folder).
- **Ubuntu security updates** install automatically (`unattended-upgrades`).
  Check it is on: `systemctl status unattended-upgrades --no-pager`. For
  everything else, now and then:
  ```bash
  sudo apt update && sudo apt upgrade
  ```
  If it says a restart is required (`/var/run/reboot-required` exists),
  `sudo reboot`. The site and nginx start by themselves.

## Settings

`/etc/categorio.env`, readable only by root and the site. After a change:
`sudo systemctl restart categorio`.

| Setting | Meaning |
|---|---|
| `CATEGORIO_SECRET_KEY` | signs login cookies. Replacing it signs everyone out; keep it private |
| `CATEGORIO_DATA` | the data folder: `/srv/categorio/data` |
| `CATEGORIO_PROXY` | `1`: behind nginx, so trust its forwarded headers |
| `CATEGORIO_SECURE_COOKIES` | `1`: send the login cookie over HTTPS only |
| `CATEGORIO_STORES_IN_MEMORY` | optional: how many user stores stay in memory (default 500) |

To view them: `sudo cat /etc/categorio.env`. To make a new secret key,
which signs everyone out, replace its line with the output of
`python3 -c 'import secrets; print(secrets.token_hex(32))'`.

## When something is wrong

| Symptom | Look at |
|---|---|
| The browser can't connect at all | is it the right address? `sudo systemctl status nginx`; `sudo ufw status` |
| "502 Bad Gateway" | the site is down: `sudo systemctl status categorio`, then its log |
| The site shows an error page | `sudo journalctl -u categorio -n 100 --no-pager` |
| Certificate warning in the browser | `sudo certbot certificates`; `sudo certbot renew` |
| An update went wrong | the updater rolls back by itself; its output says what happened. Or go back by hand (above) |
| Data looks wrong | restore a backup (above); the current data is set aside, not deleted |
| Can't log in over SSH | right key? `ssh -v peter@categor.io` shows which keys are tried. Last resort: Contabo's console |
