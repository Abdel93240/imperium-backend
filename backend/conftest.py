"""Garantit que les tests s'exécutent depuis le répertoire backend/.

Plusieurs tests lisent des fichiers via des chemins relatifs (app/..., alembic/...)
qui supposent que le cwd est backend/. Ce conftest fixe le cwd dès le chargement
de pytest, pour que la suite passe quel que soit le répertoire de lancement.
"""
import os
import pathlib

os.chdir(pathlib.Path(__file__).resolve().parent)
