#!/bin/sh
# Bring the hosted Lekha up to date with GitHub's main branch:
#     sudo sh /opt/lekha/deploy/update.sh
set -eu
cd /opt/lekha
git pull --ff-only
.venv/bin/python -m pip install --quiet -r requirements.txt
cp deploy/lekha.service deploy/lekha-backup.service deploy/lekha-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl restart lekha
systemctl --no-pager --lines=5 status lekha
