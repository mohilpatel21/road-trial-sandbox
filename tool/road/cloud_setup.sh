#!/usr/bin/env bash
# tool/road/cloud_setup.sh — THE CLOUD SETUP TEXT (B2-ROAD-A · THE ROAD, 2026-09-30; the decision map CD-16 «the cloud gets its own
# through one setup script (Flutter 3.44.6, the Python libraries), inside the ~5-minute cache», the cross-check K-18; proven in THE TRIAL
# as C1 — 86 s, «Flutter 3.44.6 • channel stable» — and C1b, C2, C3). This file is the CUSTODY COPY: the live text is pasted whole into
# the claude.ai cloud environment «becoming» (Settings → the environment → setup script), because a change there rebuilds the cache
# while a repo script it called would go stale for up to ~7 days (K-18). Changing a version is two edits in one relay: this file and the
# environment's text, EQUAL by sha256. The environment also carries four variables (its «Environment variables» field):
#   CI=true  CHROME=/opt/walk/chrome  CHROME_PATH=/opt/walk/chrome  NODE_PATH=/opt/walk/node_modules
# (CI=true: the Linux pictures, goldens/ci, are the only authority — test/flutter_test_config.dart:48-57; the walk drivers read CHROME
# or CHROME_PATH and NODE_PATH). The machine runs as root, so Chrome runs through a --no-sandbox wrapper. It never holds a token of his:
# GitHub is reached through the Claude GitHub App (CD-11). Runs before Claude Code starts; exits 0 always (a non-zero exit stops the
# session). THE TRIAL's TRIAL-ONLY block (the pre-push refusal and the gh shim) is gone: on the road main is locked on GitHub (CD-7).
set -uo pipefail
mkdir -p /opt/road && date +%s > /opt/road/setup_start
if [ ! -x /opt/flutter/bin/flutter ]; then
  curl -fsSL --retry 3 https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.44.6-stable.tar.xz | tar -xJ -C /opt || echo "FLUTTER DOWNLOAD FAILED"
fi
git config --system --add safe.directory '*'
ln -sf /opt/flutter/bin/flutter /usr/local/bin/flutter; ln -sf /opt/flutter/bin/dart /usr/local/bin/dart
flutter config --no-analytics >/dev/null 2>&1 || true
flutter precache --no-android --no-ios --no-web --no-linux --no-windows --no-macos --no-fuchsia >/dev/null 2>&1 || true
mkdir -p /opt/walk && cd /opt/walk && npm init -y >/dev/null 2>&1 && npm i jsdom@30.0.1 puppeteer-core@25.4.0 >/dev/null 2>&1 || true
curl -fsSL --retry 3 -o /tmp/chrome.zip https://storage.googleapis.com/chrome-for-testing-public/154.0.8037.92/linux64/chrome-linux64.zip && unzip -q -o /tmp/chrome.zip -d /opt/walk && rm -f /tmp/chrome.zip || true
printf '#!/bin/sh\nexec /opt/walk/chrome-linux64/chrome --no-sandbox "$@"\n' > /opt/walk/chrome && chmod +x /opt/walk/chrome
apt-get install -y -q libnss3 libatk-bridge2.0-0 libgbm1 libxkbcommon0 libasound2t64 >/dev/null 2>&1 || true
chmod -R a+rwX /opt/flutter /opt/walk /opt/road 2>/dev/null || true
flutter --version || true
date +%s > /opt/road/setup_end
exit 0
