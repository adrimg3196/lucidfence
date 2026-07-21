#!/usr/bin/env bash
set -euo pipefail
ACTION="$1"
INSTALL_DIR="${2:-/usr/local/lib/lucidfence}"
PORT="${LUCIDFENCE_PORT:-8765}"

if command -v sw_vers >/dev/null 2>&1; then
  PLIST="$HOME/Library/LaunchAgents/com.lucidfence.engine.plist"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.lucidfence.engine</string>
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
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "Installed launchd agent: $PLIST"
else
  UNIT="/etc/systemd/system/lucidfence.service"
  sudo bash -lc "cat > $UNIT <<EOF
[Unit]
Description=LucidFence engine
After=network.target

[Service]
ExecStart=$(command -v python3) $INSTALL_DIR/saas_server.py
WorkingDirectory=$INSTALL_DIR
Restart=always
Environment=PORT=$PORT

[Install]
WantedBy=multi-user.target
EOF"
  sudo bash -lc "systemctl daemon-reload && systemctl enable --now lucidfence"
  echo "Installed systemd unit: $UNIT"
fi

echo "Verify: curl -sf http://127.0.0.1:$PORT/health"
