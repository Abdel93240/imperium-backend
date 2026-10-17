"""Règles de fichiers de Nourrir l'IA (doc 70 §6, décision utilisateur 2026-10-15).

Liste blanche exacte par extension ; refus par SÉCURITÉ, pas par type de média.
25 Mo par document ou image, 500 Mo par audio ou vidéo. Les archives zip sont
dépliées côté serveur : chaque fichier interne repasse par les mêmes règles,
les archives imbriquées sont refusées, nombre et taille décompressée plafonnés.
"""

import io
import re
import unicodedata
import zipfile
from pathlib import PurePosixPath, PureWindowsPath

MB = 1024 * 1024
KINDS: dict[str, frozenset[str]] = {
    "document": frozenset({"pdf", "txt", "md", "docx", "xlsx", "csv", "odt"}),
    "image": frozenset({"jpg", "jpeg", "png", "webp", "heic"}),
    "audio": frozenset({"mp3", "m4a", "wav", "ogg", "opus"}),
    "video": frozenset({"mp4", "mov", "webm"}),
    "archive": frozenset({"zip"}),
}
SIZE_LIMITS = {"document": 25 * MB, "image": 25 * MB, "audio": 500 * MB, "video": 500 * MB, "archive": 500 * MB}
TEXT_EXTENSIONS = frozenset({"txt", "md", "csv"})
ZIP_MAX_FILES = 100
ZIP_MAX_TOTAL_BYTES = 500 * MB

# États techniques → états de la liste « Éléments transmis » (maquette 16).
UI_STATES = {
    "uploading": "to_analyze",
    "to_analyze": "to_analyze",
    "analyzing": "to_analyze",
    "to_validate": "to_validate",
    "validated": "saved",
    "vectorized": "saved",
    "failed": "error",
}


class KnowledgeFileError(ValueError):
    pass


def extension(filename: str) -> str:
    name = safe_filename(filename)
    return name.rsplit(".", 1)[1].lower() if "." in name else ""


def classify(filename: str) -> str | None:
    ext = extension(filename)
    for kind, extensions in KINDS.items():
        if ext in extensions:
            return kind
    return None


def max_bytes(kind: str) -> int:
    return SIZE_LIMITS[kind]


def safe_filename(raw: str) -> str:
    """Nom de base seul, ASCII, sans séparateurs ni caractères spéciaux."""
    base = PureWindowsPath(PurePosixPath(raw or "").name).name
    ascii_name = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._") or "fichier"
    return cleaned[:150]


def ui_state(status: str) -> str:
    return UI_STATES.get(status, "error")


def expand_zip(data: bytes) -> tuple[list[tuple[str, bytes]], list[tuple[str, str]]]:
    """Déplie une archive : (fichiers acceptés, fichiers refusés avec la raison)."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise KnowledgeFileError("Archive zip illisible.") from exc
    members = [info for info in archive.infolist() if not info.is_dir()]
    if len(members) > ZIP_MAX_FILES:
        raise KnowledgeFileError(f"Archive trop volumineuse : plus de {ZIP_MAX_FILES} fichiers.")
    if sum(info.file_size for info in members) > ZIP_MAX_TOTAL_BYTES:
        raise KnowledgeFileError("Archive trop volumineuse une fois décompressée.")
    accepted: list[tuple[str, bytes]] = []
    rejected: list[tuple[str, str]] = []
    total = 0
    for info in members:
        name = safe_filename(info.filename)
        kind = classify(name)
        if kind == "archive":
            rejected.append((name, "archive imbriquée refusée"))
            continue
        if kind is None:
            rejected.append((name, "type non accepté"))
            continue
        if info.file_size > max_bytes(kind):
            rejected.append((name, "fichier trop volumineux"))
            continue
        content = archive.read(info)
        total += len(content)
        if total > ZIP_MAX_TOTAL_BYTES:  # garde réelle contre une taille déclarée mensongère
            raise KnowledgeFileError("Archive trop volumineuse une fois décompressée.")
        accepted.append((name, content))
    return accepted, rejected
