"""Task 1717 — the EpiPen answers of the players the pre-migrate could not
reach (a database older than #1630: the boolean column only exists once
the ORM loaded and the 19.0.1.99.0 / 19.0.1.117.0 post-migrates set it).
Same mapping (True -> « yes », False / NULL -> « no »), idempotent: on a
database the pre-migrate already filled, nothing is left to do. No existing
player stays unanswered (owner 2026-10-26).
"""
import importlib.util
import os


def _pre():
    path = os.path.join(os.path.dirname(__file__), 'pre-migrate.py')
    spec = importlib.util.spec_from_file_location('bsc_1717_pre_migrate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(cr, version):
    _pre().fill_answers(cr)
