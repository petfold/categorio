# Deploying categor.io on Ubuntu 24.04

Setting up a server from scratch. For running the live site afterwards
(updates, backups, restoring, certificates, DNS, accounts), see
[ADMIN.md](ADMIN.md).

A step-by-step runbook for one VPS (written for 158.220.117.131). The site
runs as its own unprivileged user under `gunicorn`, behind `nginx`, with
HTTPS from Let's Encrypt. The files it installs are in `deploy/`.

Throughout, **replace `peter`** with the admin username you want.

The layout on the server:

| Path | What |
|---|---|
| `/srv/categorio/app` | the code (a git clone) |
| `/srv/categorio/venv` | its Python environment |
| `/srv/categorio/data` | logins and every account's store — **the part to back up** |
| `/etc/categorio.env` | settings, including the secret key |
| `/var/backups/categorio` | nightly backups |

## 1. Update the system and install what is needed

As root:

```bash
apt update && apt -y upgrade
apt -y install python3-venv python3-pip git graphviz nginx sqlite3 \
    certbot python3-certbot-nginx unattended-upgrades
```

If the upgrade installed a new kernel, `reboot` now and log in again.

## 2. Your own admin account

As root:

```bash
adduser peter                   # asks for a password: this is what sudo will ask for
usermod -aG sudo peter
install -d -m 700 -o peter -g peter /home/peter/.ssh
cp /root/.ssh/authorized_keys /home/peter/.ssh/authorized_keys
chown peter:peter /home/peter/.ssh/authorized_keys
chmod 600 /home/peter/.ssh/authorized_keys
```

**Check, keeping the root session open:** from your own computer, in a new
terminal:

```bash
ssh peter@158.220.117.131
sudo whoami                     # must print: root
```

Do not go on until this works.

## 3. Lock down SSH, and turn on the firewall

As root (or with `sudo` from the new account):

```bash
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
sshd -t && systemctl restart ssh
sshd -T | grep -E '^(permitrootlogin|passwordauthentication) '
```

The last line must print `permitrootlogin no` and `passwordauthentication
no`. The file is named `00-…` on purpose: sshd uses the *first* value it
reads, and Ubuntu's cloud image ships a `50-cloud-init.conf` that allows
passwords.

**Check again** from your computer, in a new terminal, that `ssh
peter@158.220.117.131` still works, and that `ssh root@158.220.117.131` is
now refused.

Then the firewall:

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'          # ports 80 and 443
ufw enable                      # answer y
ufw status
```

## 4. The service account and the code

```bash
sudo adduser --system --group --home /srv/categorio --shell /usr/sbin/nologin categorio
sudo -u categorio git clone https://github.com/petfold/categorio.git /srv/categorio/app
sudo -u categorio python3 -m venv /srv/categorio/venv
sudo -u categorio /srv/categorio/venv/bin/pip install -e "/srv/categorio/app[serve]"
sudo install -d -m 750 -o categorio -g categorio /srv/categorio/data
```

The install is editable (`-e`) on purpose: the site reads its user guide
from `/srv/categorio/app/docs`.

## 5. Settings

```bash
sudo install -m 640 -o root -g categorio /dev/null /etc/categorio.env
python3 -c 'import secrets; print("CATEGORIO_SECRET_KEY=" + secrets.token_hex(32))' \
    | sudo tee -a /etc/categorio.env >/dev/null
sudo tee -a /etc/categorio.env >/dev/null <<'EOF'
CATEGORIO_DATA=/srv/categorio/data
CATEGORIO_PROXY=1
CATEGORIO_SECURE_COOKIES=0
EOF
sudo cat /etc/categorio.env
```

`CATEGORIO_SECURE_COOKIES` stays `0` until HTTPS works (step 8). With `1`,
browsers would send the login cookie only over HTTPS, so signing in over
plain HTTP would fail.

## 6. Run it as a service

```bash
sudo cp /srv/categorio/app/deploy/categorio.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now categorio
sudo systemctl status categorio --no-pager
curl -sI http://127.0.0.1:8000/ | head -1        # HTTP/1.1 200 OK
```

If it is not running: `sudo journalctl -u categorio -n 50 --no-pager`.

## 7. nginx in front

```bash
sudo cp /srv/categorio/app/deploy/nginx-categorio.conf /etc/nginx/sites-available/categorio
sudo ln -s /etc/nginx/sites-available/categorio /etc/nginx/sites-enabled/categorio
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Open **http://158.220.117.131** in a browser: the site should appear.

## 8. The domain and HTTPS

1. At your domain registrar, add two DNS records:

   | Type | Name | Value |
   |---|---|---|
   | A | `@` (categor.io) | `158.220.117.131` |
   | A | `www` | `158.220.117.131` |

2. Wait until the name answers with the server's address (minutes to a
   few hours):

   ```bash
   dig +short categor.io          # 158.220.117.131
   dig +short www.categor.io      # 158.220.117.131
   ```

3. Get the certificate. certbot edits the nginx site to add HTTPS and a
   redirect from HTTP:

   ```bash
   sudo certbot --nginx -d categor.io -d www.categor.io
   ```

4. Now switch on secure cookies:

   ```bash
   sudo sed -i 's/^CATEGORIO_SECURE_COOKIES=0$/CATEGORIO_SECURE_COOKIES=1/' /etc/categorio.env
   sudo systemctl restart categorio
   ```

5. Check that renewal is scheduled, and that it works:

   ```bash
   systemctl list-timers | grep certbot
   sudo certbot renew --dry-run
   ```

Open **https://categor.io**, create an account, and sign in.

## 9. Backups

```bash
sudo cp /srv/categorio/app/deploy/backup.sh /usr/local/bin/categorio-backup
sudo chmod 755 /usr/local/bin/categorio-backup
echo '30 3 * * * root /usr/local/bin/categorio-backup' | sudo tee /etc/cron.d/categorio-backup
sudo /usr/local/bin/categorio-backup && sudo ls -l /var/backups/categorio
```

That keeps two weeks of nightly copies **on the same server**, which
protects against mistakes but not against losing the server. Copy
`/var/backups/categorio` off the machine regularly, for example from your
own computer:

```bash
rsync -av peter@158.220.117.131:/var/backups/categorio/ ~/categorio-backups/
```

(For `peter` to read the backups, which only root can by default, set up
the `categorio-backups` group once, as described in [ADMIN.md](ADMIN.md),
"Copying backups to your own computer".)

## Updating to a new version

**One command**, from your own computer:

```bash
ssh -t peter@categor.io sudo categorio-update
```

or, when already logged in as `peter`: `sudo categorio-update`.

It fetches the latest version from GitHub, shows what changed, **backs up
the data first** (into `/var/backups/categorio`, named `…-before-update`),
installs the new code, restarts the site, and checks that it answers. If
the new version does not start, it shows the site's log and **goes back to
the previous version by itself**; nothing in the data changes either way.
When there is nothing new it says so and stops.

User data and registrations are kept: they live in `/srv/categorio/data`,
which an update never touches; only `/srv/categorio/app` changes. Login
sessions survive too (the secret key is in `/etc/categorio.env`), so people
stay signed in. What is lost on a restart: the console's recent transcript
and an import preview still waiting for "Merge".

The one risk an update carries is a new version changing how data is
stored. That is what the backup before every update is for: to go back,
stop the site, restore the `…-before-update` files into
`/srv/categorio/data`, and run the previous version.

### Installing the updater (once)

```bash
sudo -u categorio git -C /srv/categorio/app pull
sudo cp /srv/categorio/app/deploy/update.sh /usr/local/bin/categorio-update
sudo cp /srv/categorio/app/deploy/backup.sh /usr/local/bin/categorio-backup
sudo chmod 755 /usr/local/bin/categorio-update /usr/local/bin/categorio-backup
```

The installed copies belong to root on purpose: running files the site's
own account can change as root would hand that account root. When an
update brings a newer `update.sh` or `backup.sh`, the updater says so and
prints the `cp` command to install it.

The updater also keeps `/etc/systemd/system/categorio.service` in step
with the repository's copy. The nginx site is left alone, since certbot
has added the HTTPS parts to it.

## When something is wrong

| Look at | Command |
|---|---|
| the site's log | `sudo journalctl -u categorio -n 100 --no-pager` |
| nginx errors | `sudo tail -n 50 /var/log/nginx/error.log` |
| is it listening | `sudo ss -ltnp \| grep -E ':80\|:443\|:8000'` |
| restart it | `sudo systemctl restart categorio` |
