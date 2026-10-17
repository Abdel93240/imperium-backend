"""Ajout au stock par le chatbot (doc 40 §11.1, doc 72 §4–§5).

« J'ai acheté 2kg de riz et 6 œufs » → lecture déterministe (sans IA) → proposition
affichée dans la conversation → l'utilisateur corrige ou retire des lignes → la
validation écrit les lignes gardées (source chatbot). Rien n'est écrit avant.

Un achat est toujours une ligne nouvelle (doc 40 §11 : une ligne par achat, dates
limites différentes) ; la proposition signale seulement le produit déjà en stock.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import FoodStockItem
from app.schemas.pulse import (
    FoodStockItemRead,
    InStockRead,
    StockDeclarationCreate,
    StockDeclarationLineRead,
    StockDeclarationPreviewRead,
    StockDeclarationRead,
)
from app.services.events.emitter import build_event
from app.services.pulse import food_stock
from app.services.pulse.pantry_scan import match_stock

MAX_LINES = 50
PAST_TOLERANCE = timedelta(days=7)  # « 20/10 » écrit le 17/10 : cette année ; « 5/1 » : l'an prochain

_SPLIT = re.compile(r"(?<!\d),|,(?!\d)|[;\n+]|\s+et\s+|\s+puis\s+", re.IGNORECASE)
_PREFIXES = re.compile(
    r"^(?:j'ai\s+(?:achet[ée]s?|pris|ramen[ée])|on\s+a\s+achet[ée]|j'ai|achet[ée]s?|achat\s+de|achat|"
    r"rajoute[rz]?|ajoute[rz]?|mets|mettre|il\s+y\s+a|aussi|encore)\b\s*",
    re.IGNORECASE,
)
_PLACE = re.compile(
    r"(?:^|\s+)(?:dans|au|à|a)\s+(?:le\s+|la\s+|l')?(?:frigo|réfrigérateur|refrigerateur|placard|congélateur|congelateur|"
    r"congel|cellier|stock)\b.*$",
    re.IGNORECASE,
)
_EXPIRY = re.compile(
    r"\(?\s*\b(dlc|ddm|p[ée]rime\s+le|expire\s+le)\s*:?\s*(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\s*\)?",
    re.IGNORECASE,
)
_DOZEN = re.compile(r"^(une\s+demi-douzaine|une\s+douzaine|deux\s+douzaines)\s+(?:de\s+|d')?", re.IGNORECASE)
_NUMBER = re.compile(r"^(\d+(?:[.,]\d+)?)\s*", re.IGNORECASE)
_WORD_NUMBERS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
    "dix": 10, "onze": 11, "douze": 12, "quinze": 15, "vingt": 20, "trente": 30,
}
_WORD = re.compile(r"^(" + "|".join(_WORD_NUMBERS) + r")\s+", re.IGNORECASE)
_HALF = re.compile(r"^demi[-\s]+", re.IGNORECASE)
_UNITS = (
    (re.compile(r"^(?:kg|kilos?|kilogrammes?)\b\.?\s*", re.IGNORECASE), "kg"),
    (re.compile(r"^(?:g|gr|grammes?)\b\.?\s*", re.IGNORECASE), "g"),
    (re.compile(r"^(?:cl|centilitres?)\b\.?\s*", re.IGNORECASE), "cl"),
    (re.compile(r"^(?:ml|millilitres?)\b\.?\s*", re.IGNORECASE), "ml"),
    (re.compile(r"^(?:l|litres?)\b\.?\s*", re.IGNORECASE), "l"),
    (re.compile(r"^(?:paquets?|bo[iî]tes?|bouteilles?|sachets?|pots?|briques?|bocaux|bocal|canettes?|packs?|"
                r"barquettes?|tranches?|filets?|bottes?|conserves?)\b\s*", re.IGNORECASE), "piece"),
)
_ARTICLE = re.compile(r"^(?:de\s+la\s+|de\s+l'|du\s+|des\s+|de\s+|d'|le\s+|la\s+|les\s+|l')", re.IGNORECASE)
_IGNORED = {"et", "puis", "aussi", "encore", "voilà", "voila", "merci", "c'est tout"}


@dataclass
class DeclaredLine:
    name: str
    quantity: Decimal
    unit: str
    quantity_assumed: bool
    expiry_type: str = "unknown"
    expiry_date: date | None = None


@dataclass
class ParsedDeclaration:
    lines: list[DeclaredLine] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_declaration(text: str, *, today: date) -> ParsedDeclaration:
    parsed = ParsedDeclaration()
    for fragment in _SPLIT.split(text.replace("’", "'")):
        line = _parse_fragment(fragment, today, parsed.warnings)
        if line is None:
            continue
        if len(parsed.lines) == MAX_LINES:
            parsed.warnings.append(f"Seuls les {MAX_LINES} premiers produits sont repris.")
            break
        parsed.lines.append(line)
    if not parsed.lines:
        parsed.warnings.append("Aucun produit compris. Écris par exemple « 2 kg de riz, 6 œufs ».")
    return parsed


def preview(db: Session, *, current_user: User, text: str, today: date) -> StockDeclarationPreviewRead:
    """Proposition affichée dans le chatbot : aucune écriture."""
    parsed = parse_declaration(text, today=today)
    stock = list(db.scalars(select(FoodStockItem).where(FoodStockItem.user_id == current_user.id, FoodStockItem.status == "active")))
    lines = []
    for index, line in enumerate(parsed.lines):
        match = match_stock(line.name, stock)
        lines.append(
            StockDeclarationLineRead(
                index=index, name=line.name, quantity=line.quantity, unit=line.unit, quantity_assumed=line.quantity_assumed,
                expiry_type=line.expiry_type, expiry_date=line.expiry_date,
                in_stock=InStockRead(stock_item_id=match.id, name=match.name, quantity=match.quantity, unit=match.unit)
                if match else None,
            )
        )
    return StockDeclarationPreviewRead(lines=lines, warnings=parsed.warnings)


def create_declaration(
    db: Session, *, current_user: User, payload: StockDeclarationCreate, idempotency_key: str, request_path: str
) -> tuple[StockDeclarationRead, bool]:
    """Écrit les lignes validées ; même clé + même contenu → même réponse, sans doublon."""
    fingerprint = food_stock.request_hash("pulse.food_stock.declaration", payload.model_dump(mode="json"))
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, StockDeclarationRead)
    if previous is not None:
        return previous, True
    declaration_id = uuid4()
    items = [
        FoodStockItem(
            user_id=current_user.id, name=line.name, quantity=line.quantity, unit=line.unit, expiry_type=line.expiry_type,
            expiry_date=line.expiry_date, category=line.category, source="chatbot",
            source_ref=f"chat:{declaration_id}:{index}", status="active", version=1,
        )
        for index, line in enumerate(payload.lines)
    ]
    db.add_all(items)
    db.flush()
    for item in items:
        db.refresh(item)
    read = StockDeclarationRead(
        declaration_id=declaration_id, stock_items=[FoodStockItemRead.model_validate(item) for item in items]
    )
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="pulse.food_stock.updated",
            payload={"source": "chatbot", "declaration_id": str(declaration_id), "items_added": len(items),
                     "stock_item_ids": [str(item.id) for item in items]},
            idempotency_key=f"pulse.food_stock.updated.chat:{declaration_id}", source_app=SourceApp.pulse,
            privacy_level=PrivacyLevel.medium,
        )
    )
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 201, read)
    db.commit()
    return read, False


# ---------- lecture d'un morceau de phrase ----------

def _parse_fragment(fragment: str, today: date, warnings: list[str]) -> DeclaredLine | None:
    text = fragment.strip(" .!?:\t")
    while (stripped := _PREFIXES.sub("", text, count=1)) != text:
        text = stripped
    text = _PLACE.sub("", text)
    expiry_type, expiry_date, bad_date = "unknown", None, False
    if found := _EXPIRY.search(text):
        text = (text[: found.start()] + " " + text[found.end():]).strip()
        expiry_date = _expiry_date(found, today)
        if expiry_date is None:
            bad_date = True
        else:
            expiry_type = "DDM" if found.group(1).lower() == "ddm" else "DLC"
    quantity, unit, text = _quantity_and_unit(text.strip())
    name = _ARTICLE.sub("", text, count=1).strip(" .!?:-")
    if not re.search(r"[^\W\d_]", name) or name.lower() in _IGNORED:
        return None
    name = name[:120]
    if bad_date:
        warnings.append(f"Date limite illisible pour « {name} » : à compléter.")
    return DeclaredLine(
        name=name, quantity=quantity if quantity is not None else Decimal("1"), unit=unit,
        quantity_assumed=quantity is None, expiry_type=expiry_type, expiry_date=expiry_date,
    )


def _quantity_and_unit(text: str) -> tuple[Decimal | None, str, str]:
    if found := _DOZEN.match(text):
        dozen = {"une demi-douzaine": 6, "une douzaine": 12, "deux douzaines": 24}[re.sub(r"\s+", " ", found.group(1).lower())]
        return Decimal(dozen), "piece", text[found.end():]
    quantity = None
    if found := _NUMBER.match(text):
        quantity, text = Decimal(found.group(1).replace(",", ".")), text[found.end():]
    elif found := _WORD.match(text):
        quantity, text = Decimal(_WORD_NUMBERS[found.group(1).lower()]), text[found.end():]
    if found := _HALF.match(text):
        quantity, text = (quantity or Decimal("1")) * Decimal("0.5"), text[found.end():]
    if quantity is None:
        return None, "piece", text
    unit = "piece"
    for pattern, name in _UNITS:
        if found := pattern.match(text):
            unit, text = name, text[found.end():]
            break
    if quantity <= 0 or quantity >= Decimal("10000000"):
        return None, "piece", text
    if quantity.as_tuple().exponent < -3:
        quantity = quantity.quantize(Decimal("0.001"))
    return quantity, unit, text


def _expiry_date(found: re.Match, today: date) -> date | None:
    day, month, year = int(found.group(2)), int(found.group(3)), found.group(4)
    try:
        if year:
            return date(int(year) + (2000 if len(year) == 2 else 0), month, day)
        guess = date(today.year, month, day)
        return guess if guess >= today - PAST_TOLERANCE else date(today.year + 1, month, day)
    except ValueError:
        return None
