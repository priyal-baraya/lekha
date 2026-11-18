# Hosting Lekha on Google Cloud (free)

This puts Lekha online at an HTTPS address that a few people can use from any device. It uses Google Cloud's **always-free** machine, so it costs nothing as long as you stay within the free limits below.

How it fits together:

- **One small machine** (an e2-micro VM running Debian 13) runs Lekha day and night.
- **Streamlit** listens only on the machine itself (`address = "localhost"`).
- **Caddy**, a web server, is the only thing open to the internet. It gets a free HTTPS certificate from Let's Encrypt, renews it by itself, and passes requests to Streamlit.
- **The data** lives in `/var/lib/lekha/data` on the machine's disk, which keeps it across restarts. Only Lekha's own user can read it.
- **A nightly backup** at 2:30 India time copies every account and shop file to `/var/lib/lekha/backups` and keeps 30 nights. It can also send them to a Cloud Storage bucket, off the machine.

The files for this are in [`deploy/`](../deploy). [`backup.py`](../backup.py) does the backups.

## Staying free

Google's free tier covers **one** e2-micro VM, a **standard** persistent disk up to 30 GB, and 5 GB of Cloud Storage, but only in **us-west1, us-central1 or us-east1**. Check the current limits on [Google's free tier page](https://cloud.google.com/free/docs/free-cloud-features#compute). Anything else (a second VM, a "balanced" disk, another region, disk snapshots) is charged.

- Google needs a card to set up billing. New accounts get a 90-day trial; when it ends, Google asks you to upgrade to a full account to keep the VM. The free-tier VM still costs nothing after that.
- Set a **budget alert** (step 1) so any charge shows up straight away.
- Don't **stop** the VM; restarting it is fine. A stopped VM gives up its address, so Lekha's web address would change.

## 1. Account, project and budget alert

1. Sign in to the [Google Cloud Console](https://console.cloud.google.com/). Use the project you made for the Google Books key, or create one.
2. Set up billing when it asks (the card step).
3. Open **Billing → Budgets & alerts → Create budget**. Choose your project, set the amount to **₹100**, and set alert thresholds at **1%** and **100%** of actual spend. Google then emails you once anything over ₹1 is charged.

## 2. A bucket and an account for backups

The VM gets its own Google account (a "service account") that can only write to one bucket, so the off-machine backups need no password.

1. **Cloud Storage → Buckets → Create.** Pick a name that's unique worldwide (for example `lekha-backups-` and some random letters). Location type **Region**, the same region you'll use for the VM (for example **us-central1**). Storage class **Standard**. Keep **Prevent public access** on.
2. In the bucket, open **Lifecycle → Add a rule → Delete object**, condition **Age: 90 days**. Old backups then delete themselves, which keeps it well under 5 GB.
3. **IAM & Admin → Service accounts → Create service account.** Name it `lekha-server`. Give it **no** roles and click **Done**.
4. Back in the bucket: **Permissions → Grant access.** Principal: the `lekha-server@…` address. Role: **Storage Object User**. Save.

## 3. Create the VM

**Compute Engine → VM instances → Create instance** (enable the Compute Engine API if asked).

| Setting | Choose |
|---|---|
| Name | `lekha` |
| Region | the bucket's region, for example **us-central1** |
| Machine type | **e2-micro** (General purpose, E2) |
| Boot disk | **Change** → Debian GNU/Linux **13**, disk type **Standard persistent disk**, size **30 GB** |
| Firewall | tick **Allow HTTP traffic** and **Allow HTTPS traffic** |
| Service account | **lekha-server**, with access scope **Allow full access to all Cloud APIs** (the bucket permission limits what it can actually do) |
| Data protection, if shown | **No backups** (snapshots aren't free; `backup.py` does this) |
| Observability, if shown | untick the Ops Agent (it uses memory the small VM needs) |

Click **Create**. When it's running, click **SSH** next to it: a terminal on the VM opens in your browser. Every command below goes there.

## 4. Install Lekha

```bash
sudo apt update && sudo apt install -y git python3-venv caddy unattended-upgrades
```

`unattended-upgrades` installs Debian's security fixes by itself.

Give the small VM 1 GB of swap, so it doesn't run out of memory while installing:

```bash
sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Make Lekha's own user (it can't sign in), then get the code and its packages:

```bash
sudo useradd --system --home-dir /var/lib/lekha --shell /usr/sbin/nologin lekha
sudo git clone https://github.com/priyal-baraya/lekha.git /opt/lekha
sudo python3 -m venv /opt/lekha/.venv
sudo /opt/lekha/.venv/bin/python -m pip install -r /opt/lekha/requirements.txt
```

The code belongs to the administrator (root), so Lekha itself can read it but never change it.

## 5. Secrets

Create the secrets file, readable only by root and Lekha:

```bash
sudo install -m 640 -o root -g lekha /dev/null /opt/lekha/.streamlit/secrets.toml
sudo nano /opt/lekha/.streamlit/secrets.toml
```

Paste in your Google Books key, the same as on your computer (see [setup.md](setup.md#optional-selling-prices-from-google-books)), then save with `Ctrl+O`, `Enter`, `Ctrl+X`:

```toml
[google_books]
api_key = "your API key"
```

Google sign-in is optional; it's in step 9.

## 6. Start Lekha and Caddy

```bash
sudo cp /opt/lekha/deploy/lekha.service /opt/lekha/deploy/lekha-backup.service /opt/lekha/deploy/lekha-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lekha lekha-backup.timer
```

Lekha's address comes from the VM's IP address and [sslip.io](https://sslip.io), a free service that turns an address like `34-123-45-67.sslip.io` back into the IP `34.123.45.67`. Caddy needs a name like this to get an HTTPS certificate:

```bash
IP=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)
ADDRESS="$(echo "$IP" | tr . -).sslip.io"
sed "s/LEKHA_ADDRESS/$ADDRESS/" /opt/lekha/deploy/Caddyfile | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
echo "Lekha is at https://$ADDRESS"
```

Open that address. The first visit can take a minute while Caddy gets the certificate. Create your account and your shop as in [setup.md](setup.md#5-create-an-account-and-your-shop), and invite the others from **Team**.

## 7. Check the backups

Run one now instead of waiting for 2:30:

```bash
sudo systemctl start lekha-backup
sudo journalctl -u lekha-backup -n 5 --no-pager
```

It should say `Backed up to /var/lib/lekha/backups/…`.

**Copy them off the machine too** (recommended: a backup on the same disk doesn't help if the VM is deleted). Replace `YOUR-BUCKET` with the bucket's name:

```bash
sudo mkdir -p /etc/systemd/system/lekha-backup.service.d
printf '[Service]\nExecStartPost=/usr/bin/gcloud storage rsync --recursive /var/lib/lekha/backups gs://YOUR-BUCKET/backups\n' | sudo tee /etc/systemd/system/lekha-backup.service.d/bucket.conf
sudo systemctl daemon-reload && sudo systemctl start lekha-backup
```

The backup folders should now appear in the bucket in the console.

## 8. Updating Lekha

After a change is merged on GitHub:

```bash
sudo sh /opt/lekha/deploy/update.sh
```

It pulls `main`, installs any new packages, and restarts Lekha. People using it at that moment are signed out (username-and-password sign-in lasts for the open tab).

## 9. Optional: Google sign-in on the hosted Lekha

Follow [setup.md](setup.md#optional-google-sign-in), with two differences:

- The redirect address is `https://` + your sslip.io address + `/oauth2callback`, in both Google's **Authorised redirect URIs** and `secrets.toml`.
- Make a **new** cookie secret on the VM: `python3 -c "import secrets; print(secrets.token_hex(32))"`.

Then `sudo systemctl restart lekha`. If Google won't accept the sslip.io address, username and password sign-in still works.

## Restoring a backup

This replaces the current data with the backup's. Pick a folder from `sudo ls /var/lib/lekha/backups`, then:

```bash
sudo systemctl stop lekha
sudo -u lekha cp -r /var/lib/lekha/backups/2026-11-18_023000/. /var/lib/lekha/data/
sudo systemctl start lekha
```

From the bucket, first copy it back: `sudo -u lekha env CLOUDSDK_CONFIG=/var/lib/lekha/.gcloud gcloud storage cp -r gs://YOUR-BUCKET/backups/2026-11-18_023000 /var/lib/lekha/backups/`.

## When something's wrong

| Problem | Look |
|---|---|
| The page doesn't load | `sudo systemctl status lekha caddy` (both should say `active (running)`), then `sudo journalctl -u lekha -n 50` |
| A certificate error | `sudo journalctl -u caddy -n 50`. Check **Allow HTTPS traffic** is ticked on the VM |
| The address changed | The VM was stopped and started. Run the step 6 commands from `IP=` again, and update Google's redirect address if you use Google sign-in |
| A backup failed | `sudo journalctl -u lekha-backup -n 20` |
