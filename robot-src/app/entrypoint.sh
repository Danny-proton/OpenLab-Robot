#!/bin/sh
set -e

/opt/chrome-linux64/chrome --headless --no-sandbox --disable-setuid-sandbox \
  --disable-dev-shm-usage --disable-gpu --remote-debugging-port=9222 --ignore-certificate-errors \
  > /dev/null 2>&1 &
sleep 2
if [ -d "/tmp/appData/skills" ]; then
  if [ ! -d "/home/appData/.claude/skills" ] || [ -z "$(ls -A /home/appData/.claude/skills 2>/dev/null)" ]; then
    mkdir -p /home/appData/.claude/skills
    cp -r /tmp/appData/skills/* /home/appData/.claude/skills/ 2>/dev/null || true
  fi
fi
if [ -f "/tmp/appData/.claude.json" ] && [ ! -f "/home/appData/.claude.json" ]; then
  cp /tmp/appData/.claude.json /home/appData/.claude.json
fi
exec "$@"