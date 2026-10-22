"""Serveur temporaire dédié à un unique ZIP documentaire, sans accès au dépôt."""

from __future__ import annotations

import argparse
import hashlib
import re
import secrets
import threading
import time
import zipfile
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def make_server(
    archive: Path, host: str, port: int, token: str, *, ttl_seconds: float = 86400
) -> ThreadingHTTPServer:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", token):
        raise ValueError("Le chemin doit être un identifiant URL aléatoire valide.")
    archive = Path(archive)
    if archive.is_symlink() or not archive.is_file() or not zipfile.is_zipfile(archive):
        raise ValueError("Une archive ZIP régulière est requise.")
    # Snapshot immuable : aucun fichier du dépôt n'est ouvert lors d'une requête.
    payload = archive.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    expires = time.monotonic() + ttl_seconds
    deadline = (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).strftime("%d/%m/%Y %H:%M UTC")
    page_path = f"/{token}/"
    zip_path = f"{page_path}Pulse_Frontend_Kit.zip"
    page = f"""<!doctype html>
<html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dossier frontend Pulse</title>
<style>
body{{background:#1a0a0d;color:#fff1ed;font:18px system-ui;margin:0;padding:24px}}
main{{max-width:660px;margin:8vh auto;padding:28px;background:#2a1015;border-radius:24px}}
h1{{font-size:2rem}}p{{line-height:1.6}}a{{display:block;background:#ff8c7a;color:#1a0a0d;
padding:20px;border-radius:14px;text-align:center;font-weight:700;text-decoration:none}}
small{{display:block;overflow-wrap:anywhere;color:#dcc4c4;margin-top:24px}}
</style><main><p>PULSE · DOSSIER DE GÉNÉRATION</p><h1>Ton frontend commence ici.</h1>
<p>Fonctionnalités, 14 écrans, parcours, design, contrats API, exemples fictifs
et prompt prêt à transmettre à ton générateur.</p>
<a href="{zip_path}" download="Pulse_Frontend_Kit.zip">Télécharger le ZIP · {len(payload) / 1024:.0f} Ko</a>
<p>Décompresse le ZIP, ouvre README.md puis 09_PROMPT_GENERATION.md.
Joins le dossier complet au générateur.</p>
<small>Lien temporaire valable jusqu'au {deadline}.<br>SHA-256 : {digest}</small>
</main></html>""".encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        server_version = "PulseDownload"
        sys_version = ""

        def setup(self) -> None:
            self.request.settimeout(15)
            super().setup()

        def log_message(self, format: str, *args: object) -> None:
            # Aucun chemin d'accès ni adresse de tablette dans les logs.
            return

        def respond(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'none'",
            )
            if status == 200 and content_type == "application/zip":
                self.send_header("Content-Disposition", 'attachment; filename="Pulse_Frontend_Kit.zip"')
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self) -> None:
            if time.monotonic() >= expires:
                self.respond(410, b"Lien expire.", "text/plain; charset=utf-8")
                return
            path = urlsplit(self.path).path
            if path == page_path:
                self.respond(200, page, "text/html; charset=utf-8")
            elif path == zip_path:
                self.respond(200, payload, "application/zip")
            else:
                self.respond(404, b"Introuvable.", "text/plain; charset=utf-8")

        def do_HEAD(self) -> None:
            self.do_GET()

        def do_POST(self) -> None:
            self.respond(405, b"Methode refusee.", "text/plain; charset=utf-8")

        do_PUT = do_POST
        do_PATCH = do_POST
        do_DELETE = do_POST
        do_OPTIONS = do_POST

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--host", default="0.0.0.0")  # nosec B104: accès tablette autorisé
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--ttl-hours", type=float, default=24)
    args = parser.parse_args()
    if not 0 < args.ttl_hours <= 168:
        parser.error("--ttl-hours doit être compris entre 0 (exclu) et 168.")
    token = secrets.token_urlsafe(24)
    server = make_server(
        args.archive, args.host, args.port, token, ttl_seconds=args.ttl_hours * 3600
    )
    timer = threading.Timer(args.ttl_hours * 3600, server.shutdown)
    timer.daemon = True
    timer.start()
    print(f"READY port={server.server_port} path=/{token}/ ttl_hours={args.ttl_hours}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        timer.cancel()
        server.server_close()


if __name__ == "__main__":
    main()
