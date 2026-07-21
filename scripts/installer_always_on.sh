#!/usr/bin/env bash
set -euo pipefail
INSTALL_DIR="${1:-/usr/local/lib/lucidfence}"
PLIST_DEST="$HOME/Library/LaunchAgents/com.lucidfence.engine.plist"
LABEL="com.lucidfence.engine"
PORT="${LUCIDFENCE_PORT:-8765}"

cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
      <string>python3</string>
      <string>$INSTALL_DIR/saas_server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/lucidfence.out.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/lucidfence.err.log</string>
  </dict>
</plist>
EOF
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"
