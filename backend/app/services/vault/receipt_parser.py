"""Lecture déterministe d'un ticket de caisse français à partir du texte OCR (doc 37 §3).

Aucun appel IA ici : on cherche l'enseigne, la date, l'heure, le total TTC et le moyen
de paiement avec des règles simples. Ce qui n'est pas trouvé reste vide et produit un
avertissement : l'utilisateur complète sur l'écran de vérification (VAU-05), et rien
n'est écrit dans le registre avant sa validation.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, time

_AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:[ .]\d{3})*|\d+)[.,](\d{2})(?!\d)")
_DATE = re.compile(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4}|\d{2})(?!\d)")
_TIME = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s?[:hH]\s?([0-5]\d)(?!\d)")
# Du plus sûr au moins sûr ; SOUS-TOTAL, TOTAL HT et TVA ne sont jamais le montant payé.
_TOTAL_LABELS = (
    re.compile(r"\b(NET\s*A\s*PAYER|TOTAL\s*TTC|MONTANT\s*TTC|A\s*PAYER)\b"),
    re.compile(r"\b(TOTAL|MONTANT|SOMME\s*DUE)\b"),
)
_NOT_TOTAL = re.compile(r"\b(SOUS[\s-]*TOTAL|TOTAL\s*HT|HT\b|TVA|RENDU|REMISE|ECONOMIE|POINTS?)\b")
_CARD = re.compile(r"\b(CB|CARTE|VISA|MASTERCARD|MAESTRO|SANS\s*CONTACT|AMEX|PAIEMENT\s*CARTE)\b")
_CASH = re.compile(r"\b(ESPECES?|ESP|CASH|LIQUIDE)\b")
_NOT_MERCHANT = re.compile(r"\b(TICKET|FACTURE|CAISSE|TEL|SIRET|TVA|DATE|BIENVENUE|MERCI|WWW|HTTP)\b|@")


@dataclass
class ParsedReceipt:
    merchant: str | None = None
    purchase_date: date | None = None
    purchase_time: time | None = None
    total_cents: int | None = None
    payment_method: str = "unknown"  # card | cash | unknown
    warnings: list[str] = field(default_factory=list)


def parse_receipt_text(raw: str) -> ParsedReceipt:
    lines = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    folded = [_fold(line) for line in lines]
    result = ParsedReceipt(
        merchant=_merchant(lines, folded),
        purchase_date=_first_date(folded),
        purchase_time=_first_time(folded),
        total_cents=_total(folded),
        payment_method=_payment(folded),
    )
    if result.merchant is None:
        result.warnings.append("Enseigne non lue.")
    if result.purchase_date is None:
        result.warnings.append("Date non lue : la date du jour est proposée.")
    if result.total_cents is None:
        result.warnings.append("Total non lu : saisis le montant.")
    elif not any(pattern.search(line) for pattern in _TOTAL_LABELS for line in folded):
        result.warnings.append("Total déduit du plus grand montant du ticket : vérifie-le.")
    return result


def _fold(line: str) -> str:
    return unicodedata.normalize("NFKD", line).encode("ascii", "ignore").decode("ascii").upper()


def _cents(match: re.Match) -> int:
    return int(re.sub(r"[ .]", "", match.group(1))) * 100 + int(match.group(2))


def _total(folded: list[str]) -> int | None:
    for pattern in _TOTAL_LABELS:
        found = None
        for index, line in enumerate(folded):
            if not pattern.search(line) or _NOT_TOTAL.search(line):
                continue
            amounts = list(_AMOUNT.finditer(line))
            if not amounts and index + 1 < len(folded):  # montant sur la ligne suivante
                amounts = list(_AMOUNT.finditer(folded[index + 1]))
            if amounts:
                found = _cents(amounts[-1])  # le dernier total du ticket fait foi
        if found:
            return found
    amounts = [_cents(match) for line in folded if not _NOT_TOTAL.search(line) for match in _AMOUNT.finditer(line)]
    return max(amounts) if amounts else None


def _first_date(folded: list[str]) -> date | None:
    for line in folded:
        for match in _DATE.finditer(line):
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            year = 2000 + year if year < 100 else year
            try:
                return date(year, month, day)
            except ValueError:
                continue
    return None


def _first_time(folded: list[str]) -> time | None:
    for line in folded:
        if re.search(r"\bTEL\b", line):
            continue
        match = _TIME.search(_DATE.sub(" ", line))
        if match:
            return time(int(match.group(1)), int(match.group(2)))
    return None


def _payment(folded: list[str]) -> str:
    text = "\n".join(folded)
    if _CARD.search(text):
        return "card"
    if _CASH.search(text):
        return "cash"
    return "unknown"


def _merchant(lines: list[str], folded: list[str]) -> str | None:
    for line, upper in zip(lines[:6], folded[:6], strict=False):
        letters = sum(char.isalpha() for char in upper)
        if letters >= 3 and not _NOT_MERCHANT.search(upper) and not _DATE.search(upper) and not _AMOUNT.search(upper):
            return line[:80]
    return None
