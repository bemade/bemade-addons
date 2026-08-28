from odoo.tests import TransactionCase

# Scans are scoped by the target's domain rather than run over every partner in
# the database: base ships partners of its own, and an unscoped scan would both
# slow the suite down and propose groups the test never created.
SCOPE = "FZTEST"


class FuzzyDedupCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Target = cls.env["bemade.dedup.target"]
        cls.Partner = cls.env["res.partner"]

    def _target(self, model="res.partner", field="ref", domain=None):
        if domain is None:
            domain = "[('function', '=', '%s')]" % SCOPE
        return self.Target.create(
            {
                "model_id": self.env["ir.model"]._get_id(model),
                "field_id": self.env["ir.model.fields"]._get(model, field).id,
                "domain": domain,
            }
        )

    def _partner(self, ref, name=None, **kw):
        vals = {"name": name or (ref or "anonymous"), "function": SCOPE, "ref": ref}
        vals.update(kw)
        return self.Partner.create(vals)

    def _pairs(self, target):
        return {frozenset(pair) for pair in target._candidate_pairs()}
