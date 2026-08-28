import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class BemadeDedupGroup(models.Model):
    _name = "bemade.dedup.group"
    _description = "Fuzzy Deduplication Group"
    _order = "id desc"

    target_id = fields.Many2one(
        "bemade.dedup.target",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_name = fields.Char(related="target_id.model_name", store=True)
    state = fields.Selection(
        [
            ("pending", "To Review"),
            ("discarded", "Discarded"),
            ("merged", "Merged"),
            ("stale", "Stale"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    record_ids = fields.One2many(
        "bemade.dedup.group.record", "group_id", string="Records"
    )
    record_count = fields.Integer(compute="_compute_record_count")
    record_names = fields.Char(
        string="Duplicates",
        compute="_compute_record_names",
        store=True,
        help="The records proposed for merging. This is what a reviewer needs "
        "to see in the list; the model and target are the same on every row.",
    )
    similarity = fields.Float(
        digits=(3, 2),
        readonly=True,
        help="Lowest trigram similarity between any two records in this group "
        "— the weakest link. A group is only as trustworthy as its least "
        "similar pair, so this is deliberately not the average.",
    )

    @api.depends("record_ids.record_name")
    def _compute_record_names(self):
        for group in self:
            names = [n for n in group.record_ids.mapped("record_name") if n]
            group.record_names = ", ".join(names) if names else False

    @api.depends("record_ids")
    def _compute_record_count(self):
        for group in self:
            group.record_count = len(group.record_ids)

    @api.depends("record_names", "model_name")
    def _compute_display_name(self):
        for group in self:
            group.display_name = group.record_names or group.model_name or ""

    def _elect_master(self):
        """Elect the oldest record as master.

        Ties on ``create_date`` are broken by id. Records created inside one
        transaction all carry that transaction's timestamp, so without the
        tie-break the election would be arbitrary rather than reproducible.
        """
        for group in self:
            records = group.record_ids._records()
            if not records:
                continue
            if "create_date" in records._fields:
                oldest = min(records, key=lambda r: (r.create_date, r.id))
            else:
                oldest = min(records, key=lambda r: r.id)
            group.record_ids.is_master = False
            group.record_ids.filtered(lambda r: r.res_id == oldest.id).is_master = True

    def action_discard(self):
        self.state = "discarded"
        return True

    def action_merge(self):
        """Merge each group into its master.

        Only ever called from the review UI. The heavy lifting is delegated to
        the model-agnostic helpers in ``base``, which is also how
        ``account_merge_wizard`` merges ``account.account`` -- there is no
        reason to reimplement foreign-key reassignment here.
        """
        for group in self:
            if group.state != "pending":
                continue
            records = group.record_ids._records()
            if len(records) != len(group.record_ids):
                # Merging the survivors would silently deliver something other
                # than what the reviewer approved.
                _logger.warning(
                    "dedup group %s references records that no longer exist; "
                    "marking it stale instead of merging",
                    group.id,
                )
                group.state = "stale"
                continue
            master_line = group.record_ids.filtered("is_master")
            if len(master_line) != 1:
                group._elect_master()
                master_line = group.record_ids.filtered("is_master")
            master = master_line._record()
            sources = records - master
            if not master or not sources:
                group.state = "stale"
                continue
            group._merge_records(master, sources)
            group.state = "merged"
        return True

    def _merge_records(self, master, sources):
        """Move everything off `sources` onto `master`, then dispose of them."""
        self.ensure_one()
        model_name = master._name
        wizard = self.env["base.partner.merge.automatic.wizard"].new()
        wizard._update_foreign_keys_generic(model_name, sources, master)
        wizard._update_reference_fields_generic(model_name, sources, master)
        # Fills fields empty on the master from the sources; the master's own
        # values win, since it is iterated last.
        wizard._update_values(sources, master)
        # Archiving is preferred over deleting where the model allows it: a
        # merge decided from a similarity score is worth being able to audit.
        if "active" in sources._fields:
            sources.write({"active": False})
        else:
            sources.unlink()
        _logger.info(
            "merged %s %s record(s) into id %s",
            len(sources),
            model_name,
            master.id,
        )


class BemadeDedupGroupRecord(models.Model):
    _name = "bemade.dedup.group.record"
    _description = "Fuzzy Deduplication Group Record"
    _order = "is_master desc, res_id"

    group_id = fields.Many2one(
        "bemade.dedup.group", required=True, ondelete="cascade", index=True
    )
    target_id = fields.Many2one(related="group_id.target_id", store=True)
    model_name = fields.Char(related="group_id.model_name", store=True)
    res_id = fields.Integer(string="Record ID", required=True, index=True)
    is_master = fields.Boolean(
        help="The record the others are merged into. Editable before merging."
    )
    record_name = fields.Char(compute="_compute_record_name")
    record_ref = fields.Reference(
        selection="_selection_record_model",
        compute="_compute_record_ref",
        string="Open",
        help="The record itself. A reviewer has to be able to open it — "
        "deciding whether two contacts are the same person usually means "
        "looking at more than the value that matched.",
    )
    details = fields.Char(
        compute="_compute_details",
        help="Distinguishing detail supplied by the model, so a group can be "
        "judged without opening every record.",
    )
    similarity = fields.Float(related="group_id.similarity", store=True)
    state = fields.Selection(related="group_id.state", store=True)
    compared_value = fields.Char(
        compute="_compute_compared_value",
        help="The value the engine actually compared. Seeing it is how a "
        "reviewer judges whether a match is real.",
    )

    @api.depends("res_id", "model_name")
    def _compute_record_name(self):
        for record in self:
            target = record._record()
            record.record_name = target.display_name if target else False

    @api.model
    def _selection_record_model(self):
        return [
            (m.model, m.name)
            for m in self.env["bemade.dedup.target"].search([]).model_id
        ]

    @api.depends("res_id", "model_name")
    def _compute_record_ref(self):
        for line in self:
            record = line._record()
            line.record_ref = "%s,%s" % (line.model_name, record.id) if record else False

    @api.depends("res_id", "model_name")
    def _compute_details(self):
        """Ask the model to describe itself for review.

        Kept as a hook rather than hard-coded columns because the engine is
        model-agnostic: only the model knows which of its fields tell two
        near-identical records apart.
        """
        for line in self:
            record = line._record()
            if record and hasattr(record, "_dedup_review_details"):
                line.details = record._dedup_review_details()
            else:
                line.details = False

    @api.depends("res_id", "group_id.target_id")
    def _compute_compared_value(self):
        for line in self:
            record = line._record()
            field = line.group_id.target_id.field_id.name
            line.compared_value = record[field] if record and field else False

    def action_merge_into(self):
        """Merge this line's group, keeping THIS record.

        The reviewer picks the survivor by acting on its row, which is the
        decision they are actually making — rather than toggling a master flag
        and then hunting for a separate merge button.
        """
        self.ensure_one()
        self.group_id.record_ids.is_master = False
        self.is_master = True
        return self.group_id.action_merge()

    def action_discard_group(self):
        """Reject the whole group from any of its rows."""
        self.ensure_one()
        return self.group_id.action_discard()

    def _record(self):
        """The underlying record, or an empty recordset if it is gone."""
        self.ensure_one()
        if not self.model_name or not self.res_id:
            return self.env["bemade.dedup.group.record"].browse()
        return self.env[self.model_name].browse(self.res_id).exists()

    def _records(self):
        """The underlying records that still exist, as one recordset."""
        if not self:
            return self.env["bemade.dedup.group.record"].browse()
        model = self.env[self[0].model_name]
        return model.browse(self.mapped("res_id")).exists()
