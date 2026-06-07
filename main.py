import subprocess
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

SCAN_DIR = Path(os.environ.get("SCAN_DIR", "/srv/scans"))
SCAN_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

app = FastAPI(title="ScannerServer")


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def scan_png() -> Path:
    ts = timestamp()
    out = SCAN_DIR / f"{ts}_scan.png"
    cmd = [
        "scanimage",
        "--format=png",
        "--resolution=300",
        f"--output-file={out}",
    ]
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        msg = result.stderr.strip() or "scanimage failed"
        log.error("scanimage error: %s", msg)
        raise RuntimeError(msg)
    log.info("Saved PNG: %s", out)
    return out


def png_to_pdf(png_path: Path) -> Path:
    pdf_path = png_path.with_suffix(".pdf")
    try:
        # Prefer img2pdf (lossless, no recompression)
        result = subprocess.run(
            ["img2pdf", str(png_path), "-o", str(pdf_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
    except FileNotFoundError:
        # Fall back to ImageMagick convert
        result = subprocess.run(
            ["convert", str(png_path), str(pdf_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "convert failed")
    log.info("Saved PDF: %s", pdf_path)
    png_path.unlink(missing_ok=True)
    return pdf_path


def scan_pdf(color_mode: str) -> Path:
    ts = timestamp()
    tmp_png = SCAN_DIR / f"{ts}_scan.png"
    cmd = [
        "scanimage",
        "--format=png",
        "--resolution=300",
        f"--mode={color_mode}",
        f"--output-file={tmp_png}",
    ]
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        msg = result.stderr.strip() or "scanimage failed"
        log.error("scanimage error: %s", msg)
        raise RuntimeError(msg)
    return png_to_pdf(tmp_png)


def list_scans() -> list[str]:
    files = sorted(SCAN_DIR.iterdir(), reverse=True)
    return [f.name for f in files if f.suffix in {".pdf", ".png"}]


# ── HTML UI ──────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ScannerServer</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 1.5rem; }}
  .buttons {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
  button {{
    padding: 0.75rem 1.5rem; font-size: 1rem; cursor: pointer;
    border: none; border-radius: 6px; color: #fff; background: #2563eb;
  }}
  button:hover {{ background: #1d4ed8; }}
  button:disabled {{ background: #93c5fd; cursor: not-allowed; }}
  #status {{ min-height: 1.5rem; margin-bottom: 1rem; color: #16a34a; font-weight: 500; }}
  #status.error {{ color: #dc2626; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #e5e7eb; }}
  th {{ background: #f9fafb; font-weight: 600; }}
  a {{ color: #2563eb; }}
</style>
</head>
<body>
<h1>ScannerServer</h1>
<div class="buttons">
  <button onclick="scan('color-pdf')">Scan Color PDF</button>
  <button onclick="scan('gray-pdf')">Scan Gray PDF</button>
  <button onclick="scan('bw-pdf')">Scan B&amp;W PDF</button>
  <button onclick="scan('png')">Scan PNG Test</button>
</div>
<div id="status"></div>
<table>
  <thead><tr><th>Fil</th><th>Ladda ned</th></tr></thead>
  <tbody>
{rows}
  </tbody>
</table>
<script>
async function scan(type) {{
  const status = document.getElementById('status');
  status.className = '';
  status.textContent = 'Skannar… (detta kan ta 10–60 sekunder)';
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  try {{
    const r = await fetch('/scan/' + type, {{ method: 'POST' }});
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Okänt fel');
    status.textContent = 'Klar: ' + data.filename;
    setTimeout(() => location.reload(), 1500);
  }} catch (e) {{
    status.className = 'error';
    status.textContent = 'Fel: ' + e.message;
    document.querySelectorAll('button').forEach(b => b.disabled = false);
  }}
}}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index():
    scans = list_scans()
    rows = "\n".join(
        f'    <tr><td>{name}</td><td><a href="/download/{name}">Ladda ned</a></td></tr>'
        for name in scans
    )
    return HTML_TEMPLATE.format(rows=rows)


# ── Scan endpoints ────────────────────────────────────────────────────────────

@app.post("/scan/color-pdf")
async def scan_color_pdf():
    try:
        path = scan_pdf("Color")
        return {"filename": path.name}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/scan/gray-pdf")
async def scan_gray_pdf():
    try:
        path = scan_pdf("Gray")
        return {"filename": path.name}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/scan/bw-pdf")
async def scan_bw_pdf():
    try:
        ts = timestamp()
        tmp_gray = SCAN_DIR / f"{ts}_scan.png"
        tmp_bw = SCAN_DIR / f"{ts}_scan_bw.png"

        # Scan in gray
        cmd = [
            "scanimage", "--format=png", "--resolution=300",
            "--mode=Gray", f"--output-file={tmp_gray}",
        ]
        log.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "scanimage failed")

        # Threshold to pure B&W with ImageMagick
        result = subprocess.run(
            ["convert", str(tmp_gray), "-threshold", "50%", str(tmp_bw)],
            capture_output=True, text=True, timeout=60,
        )
        tmp_gray.unlink(missing_ok=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "convert (threshold) failed")

        path = png_to_pdf(tmp_bw)
        return {"filename": path.name}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/scan/png")
async def scan_png_endpoint():
    try:
        path = scan_png()
        return {"filename": path.name}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/download/{filename}")
async def download(filename: str):
    # Prevent path traversal
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = SCAN_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)
