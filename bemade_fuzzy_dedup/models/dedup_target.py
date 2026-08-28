import ast
import logging

import psycopg2

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.sql import create_index, drop_index

_logger = logging.getLogger(__name__)

# PostgreSQL truncates identifiers at 63 bytes. Truncating silently would let
# two targets on long table names collide on index name, and the second would
# then reuse the first one's index -- so the name is built to fit instead.
MAX_IDENTIFIER = 63
INDEX_SUFFIX = "_trgm_idx"

THRESHOLD_PARAM = "bemade_fuzzy_dedup.similarity_threshold"
DEFAULT_THRESHOLD = 0.55


class BemadeDedupTarget(models.Model):
    _name = "bemade.dedup.target"
    _description = "Fuzzy Deduplication Target"
    _order = "model_name, field_name"

    model_id = fields.Many2one(
        "ir.model",
        required=True,
        ondelete="cascade",
        domain=[("transient", "=", False)],
    )
    model_name = fields.Char(related="model_id.model", store=True, index=True)
    field_id = fields.Many2one(
        "ir.model.fields",
        required=True,
        ondelete="cascade",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ('char', 'text')),"
        " ('store', '=', True)]",
        help="Field compared by trigram similarity. Where a model wants more "
        "than pg_trgm's own case and punctuation folding -- stripping legal "
        "suffixes from company names, say -- it supplies a stored normalised "
        "field and this points at that.",
    )
    field_name = fields.Char(related="field_id.name", store=True)
    domain = fields.Char(
        default="[]",
        required=True,
        help="Restricts which records take part. Archived records are always "
        "excluded.",
    )
    active = fields.Boolean(default=True)
    group_ids = fields.One2many(
        "bemade.dedup.group", "target_id", string="Duplicate Groups"
    )
    group_count = fields.Integer(compute="_compute_group_count")
    index_name = fields.Char(
        readonly=True,
        copy=False,
        help="Trigram index backing this target. Empty where pg_trgm is "
        "unavailable, in which case scanning is skipped.",
    )

    _model_field_uniq = models.Constraint(
        "UNIQUE (model_id, field_id)",
        "A deduplication target already exists for this model and field.",
    )

    @api.depends("group_ids.state")
    def _compute_group_count(self):
        for target in self:
            target.group_count = len(
                target.group_ids.filtered(lambda g: g.state == "pending")
            )

    @api.constrains("model_id", "field_id")
    def _check_field_on_model(self):
        for target in self:
            field = target.field_id
            if field.model_id != target.model_id:
                raise ValidationError(
                    self.env._(
                        "Field %(field)s does not belong to model %(model)s.",
                        field=field.name,
                        model=target.model_id.model,
                    )
                )
            if field.ttype not in ("char", "text") or not field.store:
                raise ValidationError(
                    self.env._(
                        "%(field)s must be a stored char or text field to be "
                        "compared by trigram similarity.",
                        field=field.name,
                    )
                )

    # ------------------------------------------------------------------
    # pg_trgm
    # ------------------------------------------------------------------
    def _ensure_pg_trgm(self):
        """Ensure the pg_trgm extension exists; return whether it does.

        Odoo creates pg_trgm in `_initialize_db`, so it is present on any
        database Odoo itself created -- but not necessarily on one built by
        `createdb` + restore, nor in every CI image. Assuming it exists made
        module installation abort the whole registry load with "operator class
        gin_trgm_ops does not exist", which is a far worse failure than not
        having the feature.

        pg_trgm is a trusted extension on PostgreSQL 13+, so the database
        owner can create it without superuser -- which is the common case on
        managed Postgres, and why this does not test for superuser first.
        """
        cr = self.env.cr
        cr.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
        if cr.rowcount:
            return True
        try:
            # A failed statement poisons the transaction, so isolate the
            # attempt: this can run during module loading.
            with cr.savepoint():
                cr.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        except psycopg2.Error as e:
            _logger.warning(
                "pg_trgm is unavailable (%s). Fuzzy deduplication scans are "
                "disabled; targets remain configurable.",
                e,
            )
            return False
        _logger.info("created the pg_trgm extension")
        return True

    # ------------------------------------------------------------------
    # SQL expression + index
    # ------------------------------------------------------------------
    def _trgm_expression(self, alias=None):
        """SQL expression holding the comparable value.

        Translated fields are JSONB in Odoo 19, so the en_US value is pulled
        out rather than comparing the whole document -- trigrams taken over
        the raw JSONB would match on its keys and on other languages.

        The scan and the index must agree on this expression exactly. A
        mismatch does not raise; it silently stops using the index.
        """
        self.ensure_one()
        column = '"%s"' % self.field_id.name
        if alias:
            column = '%s.%s' % (alias, column)
        if self.field_id.translate:
            return "(%s->>'en_US')" % column
        return column

    def _table_name(self):
        self.ensure_one()
        return self.env[self.model_name]._table

    def _index_name(self):
        self.ensure_one()
        stem = "%s__%s" % (self._table_name(), self.field_id.name)
        return stem[: MAX_IDENTIFIER - len(INDEX_SUFFIX)] + INDEX_SUFFIX

    def _create_trgm_index(self):
        for target in self:
            if not target._ensure_pg_trgm():
                continue
            name = target._index_name()
            # Declared here rather than with fields.Char(index="trigram") on
            # the target's model: Odoo's generator wraps the column in
            # unaccent() if and only if registry.has_unaccent is INDEXABLE,
            # which depends on a superuser having marked unaccent() IMMUTABLE
            # on this database. That varies by deployment and can change
            # later, and the scan queries the bare expression -- a mismatch
            # would silently stop using the index instead of failing.
            create_index(
                self.env.cr,
                name,
                target._table_name(),
                ["%s gin_trgm_ops" % target._trgm_expression()],
                method="gin",
            )
            target.index_name = name

    def _drop_trgm_index(self):
        for target in self:
            if target.index_name:
                drop_index(self.env.cr, target.index_name, target._table_name())
                target.index_name = False

    @api.model_create_multi
    def create(self, vals_list):
        targets = super().create(vals_list)
        targets._create_trgm_index()
        return targets

    def write(self, vals):
        rebuild = {"model_id", "field_id"} & vals.keys()
        if rebuild:
            self._drop_trgm_index()
        res = super().write(vals)
        if rebuild:
            self._create_trgm_index()
        return res

    def unlink(self):
        self._drop_trgm_index()
        return super().unlink()

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------
    def _similarity_threshold(self):
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

    def _scope_clause(self, model):
        """Extra SQL restricting which pairs may be compared.

        Two records under *different* parents are never duplicates of each
        other however alike their values, because child records are commonly
        named for a role rather than an identity -- "Accounts Payable",
        "Reception" -- and every parent has one. Comparing across parents
        collapses hundreds of unrelated records into a single group.
        """
        self.ensure_one()
        field = model._fields.get("parent_id")
        if field is not None and field.store:
            return "AND a.parent_id IS NOT DISTINCT FROM b.parent_id"
        return ""

    def _candidate_pairs(self):
        """Return [(id_a, id_b), ...] of records similar above the threshold.

        Equal values are included. The Enterprise arrangement excluded them
        because its exact-match rule pass had already grouped those; this
        engine is a single pass, so excluding them here would mean exact
        duplicates are never proposed at all.
        """
        self.ensure_one()
        # Without pg_trgm there is no `%` operator and the query below would
        # raise. Degrade rather than fail.
        if not self._ensure_pg_trgm():
            _logger.warning(
                "%s: skipping scan, pg_trgm is not available", self.display_name
            )
            return []
        model = self.env[self.model_name]
        # This reads the column with raw SQL, so pending ORM writes must reach
        # the table first. Without this a record whose value was just written
        # reads as NULL and silently drops out of the comparison.
        self.env.flush_all()
        # Respects active_test, so archived records are excluded, and applies
        # the target's own domain.
        eligible = model.search(ast.literal_eval(self.domain or "[]"))
        if len(eligible) < 2:
            return []
        expr_a = self._trgm_expression("a")
        expr_b = self._trgm_expression("b")
        # Validated float, and PostgreSQL does not accept a bind parameter for
        # SET, so interpolation is both necessary and safe here.
        self.env.cr.execute(
            "SET LOCAL pg_trgm.similarity_threshold = %s" % self._similarity_threshold()
        )
        self.env.cr.execute(
            """
            SELECT a.id, b.id
              FROM {table} a
              JOIN {table} b ON a.id < b.id
             WHERE a.id = ANY(%s) AND b.id = ANY(%s)
               AND {expr_a} %% {expr_b}
               AND {expr_a} <> '' AND {expr_b} <> ''
               {scope}
            """.format(
                table=self._table_name(),
                expr_a=expr_a,
                expr_b=expr_b,
                scope=self._scope_clause(model),
            ),
            (eligible.ids, eligible.ids),
        )
        return self.env.cr.fetchall()

    def _cluster(self, pairs):
        """Group pairs into connected components (union-find).

        A~B and B~C is one cluster of three, not two clusters of two.
        """
        parent = {}

        def find(node):
            parent.setdefault(node, node)
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        for left, right in pairs:
            root_left, root_right = find(left), find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        clusters = {}
        for node in parent:
            clusters.setdefault(find(node), set()).add(node)
        return [ids for ids in clusters.values() if len(ids) > 1]

    def _existing_clusters(self):
        """Sets of res_ids already grouped for this target, in any state.

        Discarded and merged groups are deliberately included: a group the
        reviewer rejected must not be resurrected by the next scan.
        """
        self.ensure_one()
        self.env.cr.execute(
            """
            SELECT ARRAY_AGG(r.res_id ORDER BY r.res_id)
              FROM bemade_dedup_group_record r
              JOIN bemade_dedup_group g ON g.id = r.group_id
             WHERE g.target_id = %s
             GROUP BY r.group_id
            """,
            (self.id,),
        )
        return [set(row[0]) for row in self.env.cr.fetchall()]

    def _scan(self):
        """Propose duplicate groups. Never merges.

        A similarity score is not an identity proof, so disposal stays with
        the reviewer whatever the configuration says.
        """
        created = self.env["bemade.dedup.group"]
        for target in self:
            pairs = target._candidate_pairs()
            if not pairs:
                continue
            seen = target._existing_clusters()
            for cluster in target._cluster(pairs):
                # Subset rather than equality: a strictly larger cluster is
                # new information and is proposed, while a repeat of one
                # already reviewed is not.
                if any(cluster <= existing for existing in seen):
                    continue
                group = self.env["bemade.dedup.group"].create(
                    {
                        "target_id": target.id,
                        "record_ids": [
                            fields.Command.create({"res_id": res_id})
                            for res_id in sorted(cluster)
                        ],
                    }
                )
                group._elect_master()
                seen.append(cluster)
                created |= group
            _logger.info(
                "%s: proposed %s group(s) from %s pair(s)",
                target.display_name,
                len(created),
                len(pairs),
            )
        return created

    def action_scan(self):
        """Scan now, then show whatever is waiting for review."""
        self._scan()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "bemade_fuzzy_dedup.bemade_dedup_group_action"
        )
        action["domain"] = [("target_id", "in", self.ids), ("state", "=", "pending")]
        return action

    @api.model
    def _cron_scan(self):
        self.search([])._scan()
