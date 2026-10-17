"""Service OCR (rôle ocr_service, doc 03) + extraction locale des documents bureautiques.

Le service tourne sur la Tower, exposé UNIQUEMENT sur son IP Tailscale, comme le
service d'embeddings. Contrat (ops/gpu/OCR_SMOKE_CHECKLIST.md) :
  POST /ocr  corps brut (le fichier), Content-Type, X-Filename
             → {"text": "...", "confidence": 0.0..1.0 | null, "pages": int | null}
  GET  /health → 200
Né désactivé (OCR_ENABLED=false). Service injoignable → OcrServiceUnreachable, que
les jobs transforment en « réessayer plus tard », jamais en échec.

Les docx, odt et xlsx n'ont pas besoin d'OCR : leur texte est lu localement
(zip + XML, bibliothèque standard, taille décompressée plafonnée).
"""

import io
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree  # nosec B405 - expat >= 2.4 protège des expansions d'entités ; XML issu d'un zip plafonné

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

OCR_EXTENSIONS = frozenset({"pdf", "jpg", "jpeg", "png", "webp", "heic"})
OFFICE_EXTENSIONS = frozenset({"docx", "odt", "xlsx"})
OFFICE_XML_MAX_BYTES = 20 * 1024 * 1024
TEXT_MAX_CHARS = 100_000

_OFFICE_PARTS = {
    "docx": re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$"),
    "odt": re.compile(r"^content\.xml$"),
    "xlsx": re.compile(r"^xl/(sharedStrings|worksheets/sheet\d+)\.xml$"),
}


class OcrServiceUnreachable(RuntimeError):
    """Le service OCR de la Tower ne répond pas : on réessaie plus tard."""


class OcrError(RuntimeError):
    pass


@dataclass
class OcrResult:
    text: str
    confidence: float | None = None
    pages: int | None = None


def ocr_available(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.ocr_enabled and settings.ocr_base_url)


def recognize(data: bytes, *, filename: str, content_type: str | None, settings: Settings | None = None) -> OcrResult:
    settings = settings or get_settings()
    if not ocr_available(settings):
        raise OcrServiceUnreachable("OCR désactivé ou OCR_BASE_URL absent.")
    url = settings.ocr_base_url.rstrip("/") + "/ocr"
    if not url.startswith(("http://", "https://")):
        raise OcrServiceUnreachable("OCR_BASE_URL invalide.")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": content_type or "application/octet-stream",
            "X-Filename": urllib.parse.quote(filename),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # nosec B310 - URL interne Tailscale configurée
            request, timeout=settings.ocr_request_timeout_seconds
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OcrServiceUnreachable(f"Service OCR injoignable : {exc}") from exc
    except ValueError as exc:
        raise OcrError("Réponse OCR illisible.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        raise OcrError("Réponse OCR mal formée.")
    confidence = payload.get("confidence")
    pages = payload.get("pages")
    return OcrResult(
        text=payload["text"][:TEXT_MAX_CHARS],
        confidence=float(confidence) if isinstance(confidence, int | float) else None,
        pages=pages if isinstance(pages, int) else None,
    )


def health_check(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.ocr_base_url:
        return False
    url = settings.ocr_base_url.rstrip("/") + "/health"
    if not url.startswith(("http://", "https://")):
        return False
    try:
        with urllib.request.urlopen(  # nosec B310 - URL interne Tailscale configurée
            urllib.request.Request(url, method="GET"), timeout=settings.ocr_request_timeout_seconds
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def extract_office_text(data: bytes, ext: str) -> str:
    """Texte d'un docx, odt ou xlsx ; OcrError si le fichier est illisible."""
    pattern = _OFFICE_PARTS.get(ext)
    if pattern is None:
        raise OcrError(f"Format non bureautique : {ext}.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise OcrError("Document illisible.") from exc
    parts = sorted((info for info in archive.infolist() if pattern.match(info.filename)), key=lambda info: _part_order(info.filename))
    if sum(info.file_size for info in parts) > OFFICE_XML_MAX_BYTES:
        raise OcrError("Document trop volumineux une fois décompressé.")
    roots = {}
    for info in parts:
        try:
            roots[info.filename] = ElementTree.fromstring(archive.read(info))  # nosec B314 - voir l'import
        except ElementTree.ParseError as exc:
            raise OcrError("Document illisible.") from exc
    if ext == "xlsx":
        chunks = _xlsx_chunks(roots)
    else:
        chunks = [_flatten(root) for root in roots.values()]
    text = re.sub(r"[ \t]+\n", "\n", "\n".join(chunk for chunk in chunks if chunk.strip()))
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:TEXT_MAX_CHARS]


def _part_order(name: str) -> tuple[int, int, str]:
    # Corps avant en-têtes et pieds, puis ordre numérique (sheet2 avant sheet10).
    number = re.search(r"(\d+)\.xml$", name)
    return (0 if name.endswith(("document.xml", "content.xml")) else 1, int(number.group(1)) if number else 0, name)


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _flatten(element) -> str:
    """docx (w:p/w:r/w:t) et odt (text:p, text:span, text:s) : texte et sauts de ligne."""
    out: list[str] = []

    def walk(node) -> None:
        name = _local(node.tag)
        if name == "s":
            out.append(" ")
        elif name in {"t", "p", "h", "span"} and node.text:
            out.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                out.append(child.tail)
        if name in {"p", "h", "tr", "table-row", "br", "line-break"}:
            out.append("\n")
        elif name in {"tab", "tc", "table-cell"}:
            out.append("\t")

    walk(element)
    return "".join(out)


def _xlsx_chunks(roots: dict) -> list[str]:
    shared: list[str] = []
    for name, root in roots.items():
        if name.endswith("sharedStrings.xml"):
            shared = ["".join(t.text or "" for t in si.iter() if _local(t.tag) == "t") for si in root if _local(si.tag) == "si"]
    chunks = []
    for name, root in roots.items():
        if "worksheets/" not in name:
            continue
        rows = []
        for row in (node for node in root.iter() if _local(node.tag) == "row"):
            cells = []
            for cell in (node for node in row if _local(node.tag) == "c"):
                kind = cell.get("t")
                value = next((node.text or "" for node in cell if _local(node.tag) == "v"), "")
                if kind == "s" and value.isdigit() and int(value) < len(shared):
                    value = shared[int(value)]
                elif kind == "inlineStr":
                    value = "".join(t.text or "" for t in cell.iter() if _local(t.tag) == "t")
                cells.append(value)
            if any(cell.strip() for cell in cells):
                rows.append("\t".join(cells).rstrip("\t"))
        chunks.append("\n".join(rows))
    return chunks
