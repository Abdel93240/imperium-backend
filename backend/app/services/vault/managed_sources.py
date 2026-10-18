"""Sources de transactions pilotées par un autre module : elles se corrigent depuis ce module.

Le registre (services/imperium/vault_transactions.py) reste générique et ne connaît pas ces
modules ; il consulte seulement cette table au moment d'une correction (VAU-08).
"""

CORRECTION_BLOCKED_SOURCES = {"path_sadaqa": "Corrige ce don depuis Path (sadaqa)."}
