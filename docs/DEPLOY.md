# Deploying categor.io on Ubuntu 24.04

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

(`peter` needs to read the folder: `sudo chgrp -R peter /var/backups/categorio`
and `sudo chmod -R g+rX /var/backups/categorio`, or run the rsync with sudo on
the server side.)

## Updating to a new version

```bash
sudo -u categorio git -C /srv/categorio/app pull
sudo -u categorio /srv/categorio/venv/bin/pip install -e "/srv/categorio/app[serve]"
sudo systemctl restart categorio
```

If `deploy/categorio.service` or `deploy/nginx-categorio.conf` changed in the
update, copy them again as in steps 6 and 7. The certbot additions live in
the installed nginx file, so merge by hand rather than overwrite it.

## When something is wrong

| Look at | Command |
|---|---|
| the site's log | `sudo journalctl -u categorio -n 100 --no-pager` |
| nginx errors | `sudo tail -n 50 /var/log/nginx/error.log` |
| is it listening | `sudo ss -ltnp \| grep -E ':80\|:443\|:8000'` |
| restart it | `sudo systemctl restart categorio` |
