#!/bin/bash
# Sync Chinnu code from the server + PiDog into this repo, commit, push.
set -e
cd "$(dirname "$0")"
EXC=(--exclude venv --exclude __pycache__ --exclude logs --exclude '*.bak*' --exclude .env --exclude cync_auth.json --exclude telegram_owner.json --exclude picovoice.key --exclude memory.json --exclude reminders.json)
echo ">> server"; rsync -az --delete "${EXC[@]}" dk@chinnu-server:chinnu-agent/ server/
rsync -az dk@chinnu-server:cync_mesh.yaml server/cync_mesh.yaml
rsync -az dk@chinnu-server:.fauxmo/config.json server/fauxmo-config.json
rsync -az dk@chinnu-server:.config/autostart/chinnu-dashboard.desktop server/chinnu-dashboard.desktop 2>/dev/null || true
echo ">> pidog"; rsync -az --delete "${EXC[@]}" dk@dkpidog:chinnu-controller/ pidog/
ssh dk@dkpidog 'cat /etc/systemd/system/chinnu-controller.service' > pidog/chinnu-controller.service 2>/dev/null || true
ssh dk@dkpidog 'cat /etc/chinnu-controller.env 2>/dev/null | sed "s/=.*/=<redacted>/"' > pidog/chinnu-controller.env.example 2>/dev/null || true
cp ~/.ssh/config mac/ssh-config 2>/dev/null || true
git add -A
if git diff --cached --quiet; then echo "no changes"; else git commit -q -m "backup $(date '+%Y-%m-%d %H:%M')" && git push -q && echo "pushed"; fi
