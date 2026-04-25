#!/usr/bin/env bash
# Strat-OS — Raspberry Pi deployment script
# Usage: bash setup.sh
# Tested on Raspberry Pi OS Lite 64-bit (Debian Bookworm)
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_USER="${SUDO_USER:-$USER}"
VENV="$REPO_DIR/.venv"
HOTSPOT_SSID="STRAT-OS-PIT"
HOTSPOT_PASS="kartdata2025"
IFACE="wlan0"
HOTSPOT_IP="192.168.4.1"

echo "================================================"
echo "  Strat-OS Setup — EV Kart Race Engineering"
echo "================================================"
echo "Repo: $REPO_DIR"
echo "User: $SERVICE_USER"
echo ""

# ── 1. System packages ────────────────────────────────────────────────────────
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3-pip python3-venv python3-dev \
    nodejs npm git \
    hostapd dnsmasq \
    libatlas-base-dev   # numpy on Pi

# ── 2. Python virtualenv ──────────────────────────────────────────────────────
echo "[2/7] Setting up Python virtualenv..."
python3 -m venv "$VENV"
source "$VENV/bin/activate"
pip install --upgrade pip setuptools wheel --quiet
pip install -r "$REPO_DIR/backend/requirements.txt" --quiet
deactivate

# ── 3. Frontend build ─────────────────────────────────────────────────────────
echo "[3/7] Building frontend..."
cd "$REPO_DIR/frontend"
npm ci --silent
npm run build
cd "$REPO_DIR"

# ── 4. Data directories ───────────────────────────────────────────────────────
echo "[4/7] Creating data directories..."
mkdir -p "$REPO_DIR/data" "$REPO_DIR/uploads" "$REPO_DIR/exports"
chmod 755 "$REPO_DIR/data" "$REPO_DIR/uploads" "$REPO_DIR/exports"

# ── 5. systemd service ────────────────────────────────────────────────────────
echo "[5/7] Installing systemd service..."
sudo tee /etc/systemd/system/stratos.service > /dev/null <<EOF
[Unit]
Description=Strat-OS EV Kart Analyzer
After=network.target

[Service]
WorkingDirectory=$REPO_DIR
# Auto-update if online (fails silently if offline)
ExecStartPre=/bin/bash -c 'git -C $REPO_DIR pull --ff-only 2>/dev/null && cd $REPO_DIR/frontend && npm ci --silent && npm run build 2>/dev/null || true'
ExecStart=$VENV/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5
User=$SERVICE_USER
Environment=PYTHONPATH=$REPO_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable stratos.service
sudo systemctl restart stratos.service
echo "    ✓ Service started on port 8000"

# ── 6. Wi-Fi hotspot ──────────────────────────────────────────────────────────
echo "[6/7] Configuring Wi-Fi hotspot..."

sudo systemctl stop hostapd dnsmasq 2>/dev/null || true

sudo tee /etc/hostapd/hostapd.conf > /dev/null <<EOF
interface=$IFACE
driver=nl80211
ssid=$HOTSPOT_SSID
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
wpa=2
wpa_passphrase=$HOTSPOT_PASS
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

sudo sed -i 's|#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd 2>/dev/null || \
  echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee -a /etc/default/hostapd

# Static IP for wlan0
if ! grep -q "interface $IFACE" /etc/dhcpcd.conf 2>/dev/null; then
  sudo tee -a /etc/dhcpcd.conf > /dev/null <<EOF

interface $IFACE
    static ip_address=$HOTSPOT_IP/24
    nohook wpa_supplicant
EOF
fi

sudo tee /etc/dnsmasq.d/stratos.conf > /dev/null <<EOF
interface=$IFACE
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
# Captive portal: redirect all DNS to Pi
address=/#/$HOTSPOT_IP
EOF

sudo systemctl unmask hostapd 2>/dev/null || true
sudo systemctl enable hostapd dnsmasq
sudo systemctl restart dhcpcd 2>/dev/null || true
sudo systemctl restart hostapd dnsmasq 2>/dev/null || echo "  (hostapd/dnsmasq will start after reboot)"

# ── 7. Done ───────────────────────────────────────────────────────────────────
echo "[7/7] Verifying service..."
sleep 3
if systemctl is-active --quiet stratos; then
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    echo ""
    echo "================================================"
    echo "  ✓ Strat-OS is running!"
    echo ""
    echo "  Local network:  http://$LOCAL_IP:8000"
    echo "  Hotspot SSID:   $HOTSPOT_SSID"
    echo "  Hotspot pass:   $HOTSPOT_PASS"
    echo "  After connecting to hotspot:"
    echo "    http://$HOTSPOT_IP:8000"
    echo ""
    echo "  Logs: sudo journalctl -u stratos -f"
    echo "================================================"
else
    echo "  ⚠ Service not running yet. Check: sudo journalctl -u stratos -n 30"
fi
