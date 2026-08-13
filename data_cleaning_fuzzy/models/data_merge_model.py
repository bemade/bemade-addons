import ast
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.data_cleaning.models.data_merge_model import merge_common_lists

_logger = logging.getLogger(__name__)

THRESHOLD_PARAM = "data_cleaning_fuzzy.similarity_threshold"
DEFAULT_THRESHOLD = 0.55


class DataMergeModel(models.Model):
    _inherit = "data_merge.model"

    fuzzy_match = fields.Boolean(
        string="Trigram Matching",
        default=False,
        help="Additionally propose records whose key is similar but not "
        "identical, using PostgreSQL trigram similarity. Runs as a separate "
        "pass from the standard rules.",
    )
    fuzzy_field_id = fields.Many2one(
        "ir.model.fields",
        string="Trigram Field",
        domain="[('model_id', '=', res_model_id), ('ttype', 'in', ('char', 'text')), ('store', '=', True)]",
        ondelete="cascade",
        help="Field compared by trigram similarity. Should hold a normalized "
        "value; comparing raw names directly gives poor results.",
    )

    @api.model
    def _fuzzy_threshold(self):
        """Similarity threshold in (0, 1], from config with a safe fallback.

        Falling back matters more than it looks: a threshold of 0.0 makes the
        `%` operator match every pair in the table, so a malformed value must
        never be read as zero. Out-of-range values are rejected for the same
        reason.
        """
        raw = self.env["ir.config_parameter"].sudo().get_param(THRESHOLD_PARAM)
        if raw in (None, False, ""):
            return DEFAULT_THRESHOLD
        try:
            value = float(raw)
        except (TypeError, ValueError):
            _logger.warning(
                "%s is not a number (%r); falling back to %s",
                THRESHOLD_PARAM,
                raw,
                DEFAULT_THRESHOLD,
            )
            return DEFAULT_THRESHOLD
        if not 0 < value <= 1:
            _logger.warning(
                "%s must be in (0, 1] (got %r); falling back to %s",
                THRESHOLD_PARAM,
                value,
                DEFAULT_THRESHOLD,
            )
            return DEFAULT_THRESHOLD
        return value

    def _fuzzy_candidate_pairs(self):
        """Return [(id_a, id_b), ...] of records similar but not identical.

        Pairs whose keys are *equal* are excluded: the standard rules already
        group those, and including them here would re-propose every stage-1
        group. NULL and empty keys drop out naturally, since both `%` and `<>`
        yield NULL against NULL.
        """
        self.ensure_one()
        field = self.fuzzy_field_id.name
        res_model = self.env[self.res_model_name]
        if field not in res_model._fields:
            raise UserError(
                _("Field %(field)s does not exist on %(model)s.",
                  field=field, model=self.res_model_name)
            )
        # Without pg_trgm there is no `%` operator and the query below would
        # raise. Stage 1 is unaffected, so degrade rather than fail.
        if not self.env["res.partner"]._dedup_ensure_pg_trgm():
            _logger.warning(
                "%s: skipping trigram pass, pg_trgm is not available",
                self.name,
            )
            return []
        # This pass reads dedup_key with raw SQL, so pending ORM writes must
        # reach the table first. Without this a record whose key was just
        # computed reads as NULL and silently drops out of the comparison.
        # find_duplicates does the same for the same reason.
        self.env.flush_all()
        # Respects active_test, so archived records are excluded, and applies
        # the deduplication model's own domain.
        eligible = res_model.search(ast.literal_eval(self.domain or "[]"))
        if len(eligible) < 2:
            return []

        # Validated float, and PostgreSQL does not accept a bind parameter for
        # SET, so interpolation is both necessary and safe here.
        self.env.cr.execute(
            "SET LOCAL pg_trgm.similarity_threshold = %s" % self._fuzzy_threshold()
        )
        self.env.cr.execute(
            """
            SELECT a.id, b.id
              FROM {table} a
              JOIN {table} b ON a.id < b.id
             WHERE a.id = ANY(%s) AND b.id = ANY(%s)
               AND a.{field} %% b.{field}
               AND a.{field} <> b.{field}
            """.format(table=res_model._table, field=field),
            (eligible.ids, eligible.ids),
        )
        return self.env.cr.fetchall()

    def _fuzzy_existing_groupings(self):
        """Sets of res_ids already grouped for this model.

        Mirrors ``find_duplicates``: discarded records are deliberately
        included, so a group the reviewer rejected is not resurrected on the
        next run.
        """
        self.ensure_one()
        self.env.cr.execute(
            """
            SELECT ARRAY_AGG(res_id ORDER BY res_id ASC)
              FROM data_merge_record
             WHERE model_id = %s
             GROUP BY group_id
            """,
            (self.id,),
        )
        return [set(row[0]) for row in self.env.cr.fetchall()]

    def _find_fuzzy_duplicates(self):
        """Materialise trigram matches as standard data_merge groups.

        Never merges, whatever ``merge_mode`` says. Trigram matches are
        suggestions by construction -- the threshold is a similarity score,
        not an identity proof -- so disposal stays with the reviewer.
        """
        for dm_model in self.filtered(lambda m: m.fuzzy_match and m.fuzzy_field_id):
            pairs = dm_model._fuzzy_candidate_pairs()
            if not pairs:
                continue
            done = dm_model._fuzzy_existing_groupings()
            created = 0
            for candidate in merge_common_lists([list(p) for p in pairs]):
                candidate = set(candidate)
                if len(candidate) < 2:
                    continue
                if any(candidate <= existing for existing in done):
                    continue
                group = self.env["data_merge.group"].create(
                    {"model_id": dm_model.id}
                )
                self.env["data_merge.record"].create(
                    [{"group_id": group.id, "res_id": res_id} for res_id in candidate]
                )
                group._elect_master_record()
                done.append(candidate)
                created += 1
            _logger.info(
                "%s: trigram pass proposed %s group(s) from %s pair(s)",
                dm_model.name,
                created,
                len(pairs),
            )

    @api.model
    def _cron_find_fuzzy_duplicates(self):
        self.search([("fuzzy_match", "=", True)])._find_fuzzy_duplicates()
