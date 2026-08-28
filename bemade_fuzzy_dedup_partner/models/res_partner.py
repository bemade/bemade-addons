import re
import unicodedata

from odoo import api, fields, models

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

        False rather than "" is load-bearing: the scan filters candidates on
        the compared value being non-empty, so an empty string would make
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

    def _dedup_review_details(self):
        """One-line description used by the deduplication review screen.

        Contacts that fold to the same key are told apart by who they belong
        to and how you reach them, so that is what a reviewer is shown.
        """
        self.ensure_one()
        bits = [
            self.parent_id.display_name,
            self.email,
            self.phone,
            self.city,
        ]
        return " · ".join(b for b in bits if b) or False
