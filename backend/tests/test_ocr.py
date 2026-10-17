"""Service OCR (rôle ocr_service) + extraction locale docx/odt/xlsx — tests unitaires."""
import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from app.services.ai import ocr

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
T = 'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def _zip(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _settings(**overrides):
    base = dict(ocr_enabled=True, ocr_base_url=None, ocr_request_timeout_seconds=2)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_docx_paragraphs_and_tabs() -> None:
    body = (f'<w:document {W}><w:body><w:p><w:r><w:t>Châssis</w:t></w:r><w:r><w:tab/><w:t>Iveco Daily</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Empattement long</w:t></w:r></w:p></w:body></w:document>')
    text = ocr.extract_office_text(_zip({"word/document.xml": body, "word/styles.xml": "<x/>"}), "docx")
    assert text == "Châssis\tIveco Daily\nEmpattement long"


def test_odt_spans_spaces_and_tails() -> None:
    content = (f'<office:document-content {T}><office:body><office:text>'
               '<text:h>Titre</text:h><text:p>Le <text:span>matin</text:span><text:s/>pour l\'administratif</text:p>'
               '</office:text></office:body></office:document-content>')
    assert ocr.extract_office_text(_zip({"content.xml": content}), "odt") == "Titre\nLe matin pour l'administratif"


def test_xlsx_resolves_shared_strings_in_sheet_order() -> None:
    shared = f'<sst {S}><si><t>Carburant</t></si><si><t>Péage</t></si></sst>'
    sheet = lambda rows: f'<worksheet {S}><sheetData>{rows}</sheetData></worksheet>'  # noqa: E731
    workbook = _zip({
        "xl/sharedStrings.xml": shared,
        "xl/worksheets/sheet10.xml": sheet('<row><c t="inlineStr"><is><t>dixième</t></is></c></row>'),
        "xl/worksheets/sheet2.xml": sheet('<row><c t="s"><v>0</v></c><c><v>52.4</v></c></row>'
                                          '<row><c t="s"><v>1</v></c><c><v>8</v></c></row>'),
    })
    assert ocr.extract_office_text(workbook, "xlsx") == "Carburant\t52.4\nPéage\t8\ndixième"


def test_broken_or_oversized_documents_raise() -> None:
    with pytest.raises(ocr.OcrError):
        ocr.extract_office_text(b"pas un zip", "docx")
    with pytest.raises(ocr.OcrError):
        ocr.extract_office_text(_zip({"word/document.xml": "<w:document"}), "docx")
    with pytest.raises(ocr.OcrError):
        ocr.extract_office_text(_zip({"content.xml": "<x/>"}), "pdf")


def test_office_decompressed_size_is_capped(monkeypatch) -> None:
    monkeypatch.setattr(ocr, "OFFICE_XML_MAX_BYTES", 10)
    with pytest.raises(ocr.OcrError):
        ocr.extract_office_text(_zip({"content.xml": "<x>" + "a" * 50 + "</x>"}), "odt")


def test_disabled_or_unconfigured_ocr_is_unavailable() -> None:
    assert not ocr.ocr_available(_settings(ocr_enabled=False, ocr_base_url="http://tower:8091"))
    assert not ocr.ocr_available(_settings(ocr_base_url=None))
    with pytest.raises(ocr.OcrServiceUnreachable):
        ocr.recognize(b"x", filename="a.png", content_type="image/png", settings=_settings())


def test_unreachable_service_raises_the_retry_error() -> None:
    with pytest.raises(ocr.OcrServiceUnreachable):
        ocr.recognize(b"x", filename="a.png", content_type="image/png", settings=_settings(ocr_base_url="http://127.0.0.1:9"))
    assert ocr.health_check(_settings(ocr_base_url="http://127.0.0.1:9")) is False


@pytest.fixture()
def fake_service():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen["path"], seen["filename"] = self.path, self.headers["X-Filename"]
            seen["body"] = self.rfile.read(int(self.headers["Content-Length"]))
            payload = seen.get("reply", {"text": "TOTAL 52.40 EUR", "confidence": 0.91, "pages": 1})
            raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):  # noqa: N802
            self.send_response(200 if self.path == "/health" else 404)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", seen
    server.shutdown()


def test_recognize_sends_raw_bytes_and_parses_the_contract(fake_service) -> None:
    url, seen = fake_service
    result = ocr.recognize(b"\x89PNG", filename="ticket é.png", content_type="image/png", settings=_settings(ocr_base_url=url))
    assert (result.text, result.confidence, result.pages) == ("TOTAL 52.40 EUR", 0.91, 1)
    assert seen["path"] == "/ocr" and seen["body"] == b"\x89PNG" and seen["filename"] == "ticket%20%C3%A9.png"
    assert ocr.health_check(_settings(ocr_base_url=url)) is True


@pytest.mark.parametrize("reply", [b"pas du json", {"texte": "x"}, ["x"]])
def test_malformed_replies_are_errors_not_outages(fake_service, reply) -> None:
    url, seen = fake_service
    seen["reply"] = reply
    with pytest.raises(ocr.OcrError):
        ocr.recognize(b"x", filename="a.png", content_type="image/png", settings=_settings(ocr_base_url=url))
