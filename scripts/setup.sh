#!/usr/bin/env bash
# Strat-OS Raspberry Pi Setup Script
# Run as root (or with sudo) on a fresh Pi OS Bookworm (64-bit)
# Usage: sudo bash scripts/setup.sh
set -e

APP_USER="pi"
APP_DIR="/home/pi/strat-os"
VENV_DIR="$APP_DIR/.venv"
SSID="Strat-OS"
WIFI_PASS="stratosracing"
PI_IP="192.168.73.1"
DHCP_RANGE="192.168.73.10,192.168.73.50"

echo "============================================================"
echo "  Strat-OS Setup — Raspberry Pi"
echo "============================================================"

# ── 1. System packages ────────────────────────────────────────────────────────
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3.11-dev \
    nodejs npm \
    sqlite3 \
    hostapd dnsmasq \
    rclone cifs-utils \
    libatlas-base-dev libopenblas-dev \
    git curl

# ── 2. Python venv + backend deps ────────────────────────────────────────────
cd "$APP_DIR"
python3.11 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r backend/requirements.txt -q
echo "Backend dependencies installed."

# ── 3. Frontend build ─────────────────────────────────────────────────────────
cd "$APP_DIR/frontend"
npm ci --prefer-offline
npm run build
echo "Frontend built."
cd "$APP_DIR"

# ── 4. Database init ──────────────────────────────────────────────────────────
"$VENV_DIR/bin/python" scripts/first_boot.py

# ── 5. systemd service ────────────────────────────────────────────────────────
cat > /etc/systemd/system/strat-os.service << EOF
[Unit]
Description=Strat-OS EV Kart Race Engineering Platform
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
Restart=always
RestartSec=5
Environment=STRATOS_PI_MODE=true
Environment=STRATOS_DATA_DIR=$APP_DIR/data

[Install]
WantedBy=multi-user.target
EOF

# ── 6. Auto-update service ───────────────────────────────────────────────────
cat > /etc/systemd/system/strat-os-update.service << EOF
[Unit]
Description=Strat-OS Auto Updater
Before=strat-os.service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$APP_USER
ExecStart=$APP_DIR/scripts/auto_update.sh
RemainAfterExit=no

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable strat-os strat-os-update

# ── 7. Wi-Fi hotspot (hostapd + dnsmasq) ─────────────────────────────────────
WLAN_IF="wlan0"

cat > /etc/hostapd/hostapd.conf << EOF
interface=$WLAN_IF
driver=nl80211
ssid=$SSID
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$WIFI_PASS
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd

cat > /etc/dnsmasq.conf << EOF
interface=$WLAN_IF
dhcp-range=$DHCP_RANGE,255.255.255.0,24h
address=/strat-os.local/$PI_IP
EOF

# Static IP for hotspot interface
if ! grep -q "interface $WLAN_IF" /etc/dhcpcd.conf; then
cat >> /etc/dhcpcd.conf << EOF

interface $WLAN_IF
    static ip_address=$PI_IP/24
    nohook wpa_supplicant
EOF
fi

systemctl unmask hostapd
systemctl enable hostapd dnsmasq
systemctl restart dhcpcd

echo "Wi-Fi hotspot configured: SSID=$SSID  IP=$PI_IP"

# ── 8. Start service ──────────────────────────────────────────────────────────
systemctl start strat-os

echo ""
echo "============================================================"
echo "  Setup complete!"
echo "  Connect to Wi-Fi: $SSID  (password: $WIFI_PASS)"
echo "  Open browser: http://strat-os.local or http://$PI_IP:8000"
echo "  First-boot wizard will guide you through setup."
echo "============================================================"
