import logging
import re
import unicodedata

import psycopg2

from odoo import api, fields, models
from odoo.tools.sql import create_index

_logger = logging.getLogger(__name__)

# Legal-form tokens stripped from the end of a name. Kept deliberately short:
# every entry here is a word that some real company could also use as part of
# its actual name, so the list is a precision/recall trade-off, not a
# taxonomy. Matched as whole tokens only -- see _strip_legal_suffixes.
LEGAL_SUFFIXES = frozenset(
    {
        "co",
        "company",
        "corp",
        "corporation",
        "gmbh",
        "inc",
        "limited",
        "llc",
        "ltd",
        "ltee",
        "sa",
        "srl",
    }
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


class ResPartner(models.Model):
    _inherit = "res.partner"

    dedup_key = fields.Char(
        string="Deduplication Key",
        compute="_compute_dedup_key",
        store=True,
        readonly=True,
        help="Partner name folded to a comparable form: accents removed, "
        "lowercased, punctuation stripped and legal suffixes removed. Used to "
        "detect near-duplicate contacts.",
    )

    @api.model
    def _dedup_tokenize(self, name):
        """Fold `name` to lowercase ASCII alphanumeric tokens."""
        decomposed = unicodedata.normalize("NFKD", name)
        folded = "".join(c for c in decomposed if not unicodedata.combining(c))
        return [token for token in _NON_ALNUM.split(folded.lower()) if token]

    @api.model
    def _strip_legal_suffixes(self, tokens):
        """Drop legal-form tokens from the END of `tokens`.

        Trailing-only rather than anywhere: legal forms trail the name in
        every language we handle ("Northwind Inc.", "Bornes Ltee"), while a
        leading occurrence is usually part of the name proper. Stripping
        anywhere would turn "Corp of Engineers" into "ofengineers".

        Looping handles stacked forms such as "Foo Inc. Ltd".
        """
        result = list(tokens)
        while result and result[-1] in LEGAL_SUFFIXES:
            result.pop()
        return result

    @api.model
    def _dedup_key_for_name(self, name):
        """Return the deduplication key for `name`, or False if there is none.

        False rather than "" is load-bearing: the deduplication engine filters
        candidates with ``length(field) > 0``, so an empty string would make
        every name-less and suffix-only record group together.
        """
        if not name:
            return False
        tokens = self._strip_legal_suffixes(self._dedup_tokenize(name))
        return "".join(tokens) or False

    @api.depends("name")
    def _compute_dedup_key(self):
        for partner in self:
            partner.dedup_key = self._dedup_key_for_name(partner.name)

    @api.model
    def _dedup_ensure_pg_trgm(self):
        """Ensure the pg_trgm extension exists; return whether it does.

        Odoo creates pg_trgm in `_initialize_db`, so it is present on any
        database Odoo itself created -- but not necessarily on one built by
        `createdb` + restore, nor in every CI image. Assuming it exists made
        module installation abort the whole registry load with "operator class
        gin_trgm_ops does not exist", which is a far worse failure than not
        having the feature.

        pg_trgm is a trusted extension on PostgreSQL 13+, so the database
        owner can create it without superuser. Where even that is refused, the
        module degrades: stage 1 (exact match on the normalized key) is
        unaffected and remains useful on its own.
        """
        cr = self.env.cr
        cr.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
        if cr.rowcount:
            return True
        try:
            # A failed statement poisons the transaction, and this runs during
            # module loading, so the attempt must be isolated.
            with cr.savepoint():
                cr.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        except psycopg2.Error as e:
            _logger.warning(
                "pg_trgm is unavailable (%s). Trigram matching is disabled; "
                "normalized-key deduplication still works.",
                e,
            )
            return False
        _logger.info("created the pg_trgm extension")
        return True

    def init(self):
        super().init()
        if not self._dedup_ensure_pg_trgm():
            return
        # Declared here rather than with fields.Char(index="trigram") on
        # purpose. Odoo's generator wraps the column in unaccent() if and only
        # if registry.has_unaccent is INDEXABLE, which depends on whether a
        # superuser has run ALTER FUNCTION unaccent(text) IMMUTABLE on this
        # database. That varies across deployments and can change later, and
        # the trigram pass queries the bare column -- an expression mismatch
        # would silently stop using the index instead of failing. dedup_key is
        # already accent-folded in Python, so unaccent() on it is a no-op.
        create_index(
            self.env.cr,
            "res_partner_dedup_key_trgm_idx",
            self._table,
            ['"dedup_key" gin_trgm_ops'],
            method="gin",
        )
