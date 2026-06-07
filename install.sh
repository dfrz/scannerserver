#!/usr/bin/env bash
# ScannerServer – installationsskript för Debian
# Kör som root: sudo bash install.sh
set -euo pipefail

APP_DIR=/opt/scannerserver
SCAN_DIR=/srv/scans
SERVICE_USER=scanner

echo "==> Installerar systempaket..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    sane sane-utils \
    python3 python3-venv python3-pip \
    img2pdf \
    libsane libusb-1.0-0

echo "==> Skapar användare '$SERVICE_USER'..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi
# Ge scannertillgång
usermod -aG scanner "$SERVICE_USER" 2>/dev/null || true
# Lägg till i plugdev för USB-scanner (Canon LiDE)
usermod -aG plugdev "$SERVICE_USER" 2>/dev/null || true

echo "==> Skapar kataloger..."
mkdir -p "$APP_DIR" "$SCAN_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$SCAN_DIR"

echo "==> Kopierar applikation..."
cp main.py requirements.txt "$APP_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

echo "==> Skapar virtualenv och installerar Python-paket..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "==> Installerar systemd-service..."
cp scannerserver.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable scannerserver
systemctl restart scannerserver

IP=$(hostname -I | awk '{print $1}')
echo ""
echo "==> Klart! ScannerServer körs nu på http://${IP}:8080"
echo "    Loggar: journalctl -u scannerserver -f"
