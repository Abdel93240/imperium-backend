"""Lieux d'une offre Bolt : commune ou quartier → code postal et position (centre de la commune ou de l'arrondissement).

Sur les vraies offres Bolt, la prise en charge porte souvent un code postal (« Boulogne-Billancourt 92100 ») mais
l'arrivée presque jamais (« Suresnes », « St.-Maur-des-Fossés », « La Maison du lissage, Picpus, Paris »). Vector
résout donc le lieu avec la liste officielle des communes d'Île-de-France (geo.api.gouv.fr, figée dans
`data/communes_idf.json`) et, pour Paris, les 80 quartiers administratifs et quelques lieux connus. Une commune à
plusieurs codes postaux prend le premier (le département reste juste) ; Paris sans quartier reconnu reste sans code
(département 75 seulement). Rien n'est deviné au-delà : un lieu inconnu reste inconnu.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

QUARTERS = {
    1: ["Saint-Germain-l'Auxerrois", "Halles", "Les Halles", "Palais-Royal", "Place-Vendôme", "Châtelet", "Louvre"],
    2: ["Gaillon", "Vivienne", "Mail", "Bonne-Nouvelle", "Sentier", "Bourse"],
    3: ["Arts-et-Métiers", "Enfants-Rouges", "Archives", "Sainte-Avoye", "Marais", "Haut-Marais", "Temple"],
    4: ["Saint-Merri", "Saint-Gervais", "Arsenal", "Notre-Dame", "Île Saint-Louis", "Hôtel de Ville"],
    5: ["Saint-Victor", "Jardin-des-Plantes", "Val-de-Grâce", "Sorbonne", "Quartier Latin", "Panthéon"],
    6: ["Monnaie", "Odéon", "Notre-Dame-des-Champs", "Saint-Germain-des-Prés", "Luxembourg"],
    7: ["Saint-Thomas-d'Aquin", "Invalides", "École-Militaire", "Gros-Caillou", "Tour Eiffel"],
    8: ["Champs-Élysées", "Faubourg-du-Roule", "Madeleine", "Europe", "Saint-Lazare", "Élysée"],
    9: ["Saint-Georges", "Chaussée-d'Antin", "Faubourg-Montmartre", "Rochechouart", "Opéra", "Pigalle"],
    10: ["Saint-Vincent-de-Paul", "Porte-Saint-Denis", "Porte-Saint-Martin", "Hôpital-Saint-Louis", "Gare du Nord",
         "Gare de l'Est", "Canal Saint-Martin"],
    11: ["Folie-Méricourt", "Saint-Ambroise", "Roquette", "Sainte-Marguerite", "Bastille", "Oberkampf", "République"],
    12: ["Bel-Air", "Picpus", "Bercy", "Quinze-Vingts", "Nation", "Gare de Lyon", "Daumesnil"],
    13: ["Salpêtrière", "Gare", "Maison-Blanche", "Croulebarbe", "Place d'Italie", "Butte-aux-Cailles", "Bibliothèque"],
    14: ["Montparnasse", "Parc-de-Montsouris", "Petit-Montrouge", "Plaisance", "Alésia", "Denfert-Rochereau"],
    15: ["Saint-Lambert", "Necker", "Grenelle", "Javel", "Beaugrenelle", "Porte de Versailles", "Vaugirard"],
    16: ["Auteuil", "Muette", "Porte-Dauphine", "Chaillot", "Passy", "Trocadéro"],
    17: ["Ternes", "Plaine-de-Monceaux", "Plaine-Monceau", "Batignolles", "Épinettes", "Porte Maillot"],
    18: ["Grandes-Carrières", "Clignancourt", "Goutte-d'Or", "Chapelle", "La Chapelle", "Montmartre"],
    19: ["Villette", "La Villette", "Pont-de-Flandre", "Amérique", "Combat", "Buttes-Chaumont"],
    20: ["Belleville", "Saint-Fargeau", "Père-Lachaise", "Charonne", "Ménilmontant", "Gambetta"],
}
# Lieux nommés hors communes (aéroports) ; Beauvais est hors Île-de-France.
PLACES = {"charles de gaulle": ("95700", 49.0097, 2.5479), "roissy": ("95700", 49.0097, 2.5479),
          "cdg": ("95700", 49.0097, 2.5479), "orly": ("94390", 48.7262, 2.3652),
          "beauvais": ("60000", 49.4544, 2.1128)}
CODE = re.compile(r"\b(\d{5})\b")


@dataclass(frozen=True)
class Place:
    commune: str
    postal_code: str | None
    department: str
    lat: float
    lng: float


def _key(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    plain = re.sub(r"\bste?s?\.?(?=[\s-])", lambda m: "sainte" if m.group(0).startswith("ste") else "saint", plain)
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


@lru_cache(maxsize=1)
def _tables() -> tuple[dict, dict, dict]:
    data = json.loads(resources.files("app.services.vector").joinpath("data/communes_idf.json").read_text("utf-8"))
    communes = {_key(name): (name, codes, lat, lng) for name, codes, lat, lng, _ in data["communes"]}
    by_code = {}
    for name, codes, lat, lng, _ in data["communes"]:
        for code in codes:
            by_code.setdefault(code, (name, lat, lng))
    for code, (lat, lng) in data["paris"].items():
        by_code[code] = ("Paris", lat, lng)
    quarters = {_key(q): f"750{n:02d}" for n, names in QUARTERS.items() for q in names}
    return communes, by_code, quarters


def resolve(text: str | None) -> Place | None:
    """« 66 Avenue X, Boulogne-Billancourt 92100 », « Picpus, Paris », « St.-Maur-des-Fossés » → lieu ; sinon None."""
    if not text or not text.strip():
        return None
    communes, by_code, quarters = _tables()
    if found := CODE.search(text):
        code = found.group(1)
        if code in by_code:
            name, lat, lng = by_code[code]
            return Place(name, code, code[:2], lat, lng)
    parts = [_key(part) for part in re.split(r"[,|]", CODE.sub(" ", text)) if part.strip()]
    for part in reversed(parts):
        for place, (code, lat, lng) in PLACES.items():
            if place in part:
                return Place(part.title(), code, code[:2], lat, lng)
        if part == "paris" or part.startswith("paris "):
            district = re.search(r"paris (\d{1,2})", part)
            code = (f"750{int(district.group(1)):02d}" if district and 1 <= int(district.group(1)) <= 20
                    else next((quarters[p] for p in parts if p in quarters), None))
            if code:
                _, lat, lng = by_code[code]
                return Place("Paris", code, "75", lat, lng)
            return Place("Paris", None, "75", 48.8589, 2.347)
        if part in communes:
            name, codes, lat, lng = communes[part]
            return Place(name, codes[0], codes[0][:2], lat, lng)
    return None


@lru_cache(maxsize=1)
def densities() -> tuple[tuple[float, float, int], ...]:
    """(lat, lng, habitants/km²) du centre de chaque commune ; Paris compté par arrondissement (très dense)."""
    data = json.loads(resources.files("app.services.vector").joinpath("data/communes_idf.json").read_text("utf-8"))
    return tuple((lat, lng, density) for _, _, lat, lng, density in data["communes"]) + tuple(
        (lat, lng, 20000) for lat, lng in data["paris"].values())
