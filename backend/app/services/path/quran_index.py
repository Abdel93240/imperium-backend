"""Repères du mushaf de Médine (604 pages) : page de début de chaque sourate et de chaque juz.

Données de référence fixes, sans calcul ni IA. Une page appartient au juz dont le début
est la dernière valeur ≤ page ; la sourate de référence d'une page est la dernière qui
commence à cette page ou avant (sans découpage par ligne, une sourate qui se termine en
haut d'une page n'est pas listée). Hizb : pas encore (bornes à vérifier sur une source).
"""

PAGES = 604

# Sourates 1 à 114.
SURAH_START_PAGES = (
    1, 2, 50, 77, 106, 128, 151, 177, 187, 208, 221, 235, 249, 255, 262, 267, 282, 293, 305, 312,
    322, 332, 342, 350, 359, 367, 377, 385, 396, 404, 411, 415, 418, 428, 434, 440, 446, 453, 458, 467,
    477, 483, 489, 496, 499, 502, 507, 511, 515, 518, 520, 523, 526, 528, 531, 534, 537, 542, 545, 549,
    551, 553, 554, 556, 558, 560, 562, 564, 566, 568, 570, 572, 574, 575, 577, 578, 580, 582, 583, 585,
    586, 587, 587, 589, 590, 591, 591, 592, 593, 594, 595, 595, 596, 596, 597, 597, 598, 598, 599, 599,
    600, 600, 601, 601, 601, 602, 602, 602, 603, 603, 603, 604, 604, 604,
)

# Juz 1 à 30.
JUZ_START_PAGES = (
    1, 22, 42, 62, 82, 102, 121, 142, 162, 182, 201, 222, 242, 262, 282,
    302, 322, 342, 362, 382, 402, 422, 442, 462, 482, 502, 522, 542, 562, 582,
)


def juz_of(page: int) -> int:
    return max(index for index, start in enumerate(JUZ_START_PAGES, start=1) if start <= page)


def surah_of(page: int) -> int:
    return max(index for index, start in enumerate(SURAH_START_PAGES, start=1) if start <= page)


def surahs_on(page: int) -> list[int]:
    """Sourates qui commencent sur la page ; à défaut, celle qui s'y poursuit."""
    starting = [index for index, start in enumerate(SURAH_START_PAGES, start=1) if start == page]
    return starting or [surah_of(page)]
