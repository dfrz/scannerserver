# ScannerServer

Enkelt webbgränssnitt för att skanna med Canon LiDE via SANE på Debian.

## Snabbstart – lokal testning på Debian-servern

```bash
# Installera beroenden (en gång)
sudo apt-get install sane sane-utils img2pdf python3-venv

# Skapa virtualenv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Starta servern (skanningar hamnar i /tmp/scans om SCAN_DIR inte är satt)
SCAN_DIR=/tmp/scans uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Öppna sedan `http://<serverns-ip>:8080` i webbläsaren.

## Verifiering innan installation

```bash
# Kontrollera att scannern hittas
scanimage -L

# Testskanning till PNG
scanimage --format=png --resolution=150 --output-file=/tmp/test.png
```

## Produktionsinstallation (kör som root)

```bash
sudo bash install.sh
```

Installationsskriptet:
- Installerar systempaket (sane, img2pdf, python3)
- Skapar systemanvändaren `scanner`
- Kopierar appen till `/opt/scannerserver`
- Skapar virtualenv och installerar Python-paket
- Registrerar och startar `scannerserver.service`

## Hantera tjänsten

```bash
sudo systemctl status scannerserver
sudo systemctl restart scannerserver
sudo journalctl -u scannerserver -f      # live-loggar
```

## Felsökning

| Problem | Lösning |
|---------|---------|
| `No scanner found` | Kör `scanimage -L` som samma användare. Kontrollera USB-kabel och att `scanner`-gruppen har tillgång. |
| PDF-konvertering misslyckas | Kontrollera att `img2pdf` är installerat: `which img2pdf`. Fallback till ImageMagick `convert`. |
| Port 8080 blockerad | `sudo ufw allow 8080/tcp` eller ändra port i service-filen. |
| Scanner upptagen | Vänta tills föregående skanning är klar – gränssnittet blockerar nya anrop. |

## Projektstruktur

```
scannerserver/
├── main.py                  # FastAPI-applikation
├── requirements.txt
├── scannerserver.service    # systemd-unit
├── install.sh               # installationsskript
└── README.md
```

## Miljövariabler

| Variabel | Standard | Beskrivning |
|----------|----------|-------------|
| `SCAN_DIR` | `/srv/scans` | Katalog där skannade filer sparas |
