#!/bin/bash
# Weekly refresh of the Zapret RU Gov blocklist (see README.md).
# Re-downloads zapret.dat; if it changed, replaces the live file and force-restarts
# the Remnawave node so Xray-core picks up the new list. Cron-driven, logs to
# /var/log/zapret-refresh.log.
set -euo pipefail

LIVE_FILE=/opt/remnawave/xray/share/zapret.dat
TMP_FILE=$(mktemp)
URL="https://github.com/kutovoys/ru_gov_zapret/releases/latest/download/zapret.dat"

cleanup() { rm -f "$TMP_FILE"; }
trap cleanup EXIT

echo "[$(date -Is)] Checking for zapret.dat update..."

if ! wget -q -O "$TMP_FILE" "$URL"; then
    echo "[$(date -Is)] Download failed, keeping existing file."
    exit 1
fi

if [ ! -s "$TMP_FILE" ]; then
    echo "[$(date -Is)] Downloaded file is empty, keeping existing file."
    exit 1
fi

if [ -f "$LIVE_FILE" ] && cmp -s "$TMP_FILE" "$LIVE_FILE"; then
    echo "[$(date -Is)] No change."
    exit 0
fi

cp "$TMP_FILE" "$LIVE_FILE"
echo "[$(date -Is)] Updated $LIVE_FILE, restarting Remnawave node..."

TOKEN=$(cat /root/.remnawave_api_token)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"forceRestart": true}' \
    "https://inix-vpn.com/api/nodes/actions/restart-all")

echo "[$(date -Is)] Node restart request HTTP $HTTP_CODE"
