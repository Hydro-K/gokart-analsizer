export default function PiGuide() {
  const copy = (text: string) => navigator.clipboard?.writeText(text).catch(() => {})

  return (
    <div className="space-y-8 max-w-3xl text-sm">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Raspberry Pi Deployment Guide</h1>
        <p className="text-gray-400 mt-1">
          Run Strat-OS headlessly on a Raspberry Pi 4/5. On boot it auto-starts the server and
          broadcasts its own Wi-Fi hotspot so you can open a laptop anywhere and access all telemetry.
        </p>
      </div>

      <Section title="1. Hardware Requirements">
        <ul className="space-y-1 text-gray-300 list-disc list-inside">
          <li>Raspberry Pi 4 (4GB+ RAM recommended) or Pi 5</li>
          <li>128 GB microSD card (Class 10 / A2)</li>
          <li>Optional: USB 3.0 external HDD for raw CSV archive</li>
          <li>USB Wi-Fi adapter <em>(if Pi doesn't have built-in Wi-Fi)</em></li>
          <li>Power bank or 12V → 5V USB-C converter for pit-lane power</li>
        </ul>
      </Section>

      <Section title="2. Flash OS">
        <p className="text-gray-400 mb-2">Use <strong className="text-white">Raspberry Pi OS Lite (64-bit)</strong> — no desktop needed.</p>
        <Code>
{`# On your laptop — install rpi-imager then flash:
# Select: Raspberry Pi OS Lite (64-bit)
# Enable SSH, set hostname: strat-os
# Set username/password in advanced options`}
        </Code>
      </Section>

      <Section title="3. One-Command Setup">
        <p className="text-gray-400 mb-2">SSH in, then run the setup script. It installs everything and configures the hotspot.</p>
        <Code copyText="curl -fsSL https://raw.githubusercontent.com/your-repo/strat-os/main/setup.sh | bash" onCopy={copy}>
{`# SSH into the Pi:
ssh pi@strat-os.local

# Download and run the setup script:
curl -fsSL https://raw.githubusercontent.com/your-repo/strat-os/main/setup.sh | bash`}
        </Code>
        <p className="text-gray-500 text-xs mt-2">If you cloned the repo manually, run <code className="text-accent">bash setup.sh</code> from the project root.</p>
      </Section>

      <Section title="4. setup.sh Contents">
        <p className="text-gray-400 mb-2">Save this as <code className="text-accent">setup.sh</code> in your project root:</p>
        <Code>
{`#!/usr/bin/env bash
set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Strat-OS Setup ==="

# ── System deps ──────────────────────────────────────────────
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-venv nodejs npm hostapd dnsmasq git

# ── Python venv ───────────────────────────────────────────────
python3 -m venv "$REPO_DIR/.venv"
source "$REPO_DIR/.venv/bin/activate"
pip install --upgrade pip
pip install -r "$REPO_DIR/backend/requirements.txt"

# ── Frontend build ────────────────────────────────────────────
cd "$REPO_DIR/frontend"
npm ci --silent
npm run build
cd "$REPO_DIR"

# ── systemd service ───────────────────────────────────────────
sudo tee /etc/systemd/system/stratos.service > /dev/null <<EOF
[Unit]
Description=Strat-OS EV Kart Analyzer
After=network.target

[Service]
WorkingDirectory=$REPO_DIR
ExecStartPre=/bin/bash -c 'cd $REPO_DIR && git pull --ff-only 2>/dev/null || true'
ExecStart=$REPO_DIR/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
User=$USER
Environment=PYTHONPATH=$REPO_DIR

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable stratos.service
sudo systemctl restart stratos.service

# ── Wi-Fi hotspot (hostapd + dnsmasq) ────────────────────────
SSID="STRAT-OS-PIT"
PASSWORD="kartdata2025"
INTERFACE="wlan0"

sudo tee /etc/hostapd/hostapd.conf > /dev/null <<EOF
interface=$INTERFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

sudo sed -i 's|#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

sudo tee /etc/dnsmasq.conf > /dev/null <<EOF
interface=$INTERFACE
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/#/192.168.4.1
EOF

sudo ip addr add 192.168.4.1/24 dev $INTERFACE 2>/dev/null || true

sudo systemctl unmask hostapd
sudo systemctl enable hostapd dnsmasq
sudo systemctl restart hostapd dnsmasq 2>/dev/null || true

echo ""
echo "✓ Strat-OS installed and running."
echo "  URL (same network): http://$(hostname -I | awk '{print $1}'):8000"
echo "  Wi-Fi hotspot: SSID=$SSID  Password=$PASSWORD"
echo "  Connect laptop to STRAT-OS-PIT then open: http://192.168.4.1:8000"`}
        </Code>
      </Section>

      <Section title="5. Auto-Update on Boot">
        <p className="text-gray-300">
          The systemd service runs <code className="text-accent">git pull --ff-only</code> before starting.
          When the Pi has internet access it will pull the latest code automatically.
          When offline, it skips silently and starts with the last known version.
        </p>
      </Section>

      <Section title="6. Connecting from Your Laptop">
        <ol className="space-y-2 text-gray-300 list-decimal list-inside">
          <li>Power on the Pi. Wait ~30 seconds for boot.</li>
          <li>On your laptop, connect to Wi-Fi network: <code className="text-accent font-bold">STRAT-OS-PIT</code></li>
          <li>Password: <code className="text-accent font-bold">kartdata2025</code></li>
          <li>Open browser → <code className="text-accent font-bold">http://192.168.4.1:8000</code></li>
          <li>Log in with the admin account you created in the First Boot Wizard.</li>
        </ol>
      </Section>

      <Section title="7. Uploading Session Data">
        <p className="text-gray-300 mb-2">
          Pull the microSD from the AiM Solo 2 and connect it to the Pi via USB SD adapter,
          or copy over Wi-Fi from your laptop using the Upload page.
        </p>
        <p className="text-gray-300 mb-2">
          Each session folder from the Solo 2 contains up to 10 CSV files (<code className="text-accent">_GPS.csv</code>,
          <code className="text-accent"> _laps_and_splits.csv</code>, accelerometer channels, etc.).
          Use <strong className="text-white">Browse Folder</strong> on the Upload page to select an entire session folder —
          all channels will be merged automatically.
        </p>
        <p className="text-gray-400 text-xs">
          For bulk upload of 18+ sessions at once, select multiple folders by holding Ctrl/Cmd while clicking Browse Folder.
        </p>
      </Section>

      <Section title="8. External HDD for Archive">
        <Code>
{`# Mount a USB HDD at boot
sudo mkdir -p /mnt/archive
echo "UUID=$(sudo blkid -s UUID -o value /dev/sda1)  /mnt/archive  ext4  defaults,nofail  0  2" \\
  | sudo tee -a /etc/fstab

# Then in Settings → Storage, set Archive Path to:
# /mnt/archive`}
        </Code>
      </Section>

      <Section title="9. Troubleshooting">
        <div className="space-y-2 text-gray-300">
          <p><strong className="text-white">Service won't start:</strong> <code className="text-accent">sudo journalctl -u stratos -n 50 --no-pager</code></p>
          <p><strong className="text-white">Hotspot not visible:</strong> Run <code className="text-accent">sudo systemctl status hostapd</code> — may need to blacklist the onboard Wi-Fi module.</p>
          <p><strong className="text-white">Port already in use:</strong> Check <code className="text-accent">sudo ss -tlnp | grep 8000</code> and kill the conflicting process.</p>
          <p><strong className="text-white">Database locked:</strong> Only one instance should run. Restart: <code className="text-accent">sudo systemctl restart stratos</code></p>
        </div>
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="text-base font-bold text-white border-b border-border pb-2">{title}</h2>
      {children}
    </div>
  )
}

function Code({ children, copyText, onCopy }: { children: string; copyText?: string; onCopy?: (t: string) => void }) {
  return (
    <div className="relative group">
      <pre className="bg-surface border border-border rounded-lg p-4 text-xs text-green font-mono overflow-x-auto whitespace-pre">
        {children.trim()}
      </pre>
      {onCopy && copyText && (
        <button
          onClick={() => onCopy(copyText)}
          className="absolute top-2 right-2 text-xs text-gray-500 hover:text-accent border border-border rounded px-2 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity bg-surface"
        >
          Copy
        </button>
      )}
    </div>
  )
}
