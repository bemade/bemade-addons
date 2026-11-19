import unittest

import psycopg2

from odoo.modules.db import FunctionStatus
from odoo.orm.registry import _unaccent
from odoo.tests import TransactionCase
from odoo.tools import mute_logger
from odoo.tools.misc import remove_accents


class UnaccentKnowledgeCase(TransactionCase):
    """Make sure the ``unaccent`` extension is there for the test.

    On a database created without it (the addon CI's), the extension is
    created inside the test transaction and the registry flags Odoo computes
    when it loads the database are patched for the class, so the tests run
    the same code as on a database that has it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cr = cls.env.cr
        cr.execute("SELECT 1 FROM pg_extension WHERE extname = 'unaccent'")
        if not cr.rowcount:
            try:
                with mute_logger("odoo.sql_db"), cr.savepoint():
                    cr.execute("CREATE EXTENSION unaccent")
            except psycopg2.Error as error:
                raise unittest.SkipTest(f"unaccent extension unavailable: {error}") from None
        registry = cls.env.registry
        if not registry.has_unaccent:
            cls.classPatch(registry, "has_unaccent", FunctionStatus.PRESENT)
            cls.classPatch(registry, "unaccent", _unaccent)
            cls.classPatch(registry, "unaccent_python", remove_accents)
        cls.Article = cls.env["knowledge.article"]
        cls.Article._bemade_unaccent_body_search(enable=True)

    @classmethod
    def _article(cls, name, body="", **values):
        return cls.Article.create(
            {"name": name, "body": body, "internal_permission": "write", **values}
        )

    def _search(self, query, limit=40, model=None):
        model = model or self.Article
        model.env.flush_all()
        return model.get_sorted_articles(query, limit=limit)

    def _ids(self, results):
        return [entry["id"] for entry in results]
