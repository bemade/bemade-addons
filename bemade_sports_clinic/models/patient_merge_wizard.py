from markupsafe import Markup

from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError

# Fields resolved by an explicit rule rather than by destination-precedence.
# Never reported as conflicts: the rule, not the user, decides them.
RULE_RESOLVED_FIELDS = (
    "first_name", "last_name", "partner_id", "team_ids",
    "last_consultation_date", "match_status", "practice_status",
)
# Clinical free text: never discarded, concatenated under a provenance header.
TEXT_FIELDS = ("team_info_notes", "allergies")
# Scalars: destination wins where set, sources fill blanks.
SCALAR_FIELDS = ("date_of_birth", "predicted_return_date", "return_date")
# Destination always wins; sources never fill (a False is a real value here).
DEST_ONLY_FIELDS = ("pending_removal",)
# Compared when looking for conflicts to warn about.
CONFLICT_FIELDS = SCALAR_FIELDS + TEXT_FIELDS + DEST_ONLY_FIELDS
# Suppress the follower email storm. last_consultation_date, match_status,
# practice_status, predicted_return_date and return_date are all in
# patient.external_tracking_fields and notify the team on change.
QUIET = {
    "tracking_disable": True,
    "mail_notrack": True,
    "mail_auto_subscribe_no_notify": True,
    "mail_create_nosubscribe": True,
}


class PatientMergeWizard(models.TransientModel):
    _name = "sports.patient.merge.wizard"
    _description = "Merge Players"

    patient_ids = fields.Many2many(
        "sports.patient",
        string="Players to merge",
        required=True,
    )
    dst_patient_id = fields.Many2one(
        "sports.patient",
        string="Player to keep",
        required=True,
        domain="[('id', 'in', patient_ids)]",
        help="The surviving record. Where two players disagree on a field, "
             "this one's value is kept.",
    )
    conflict_info = fields.Html(
        string="Please review", compute="_compute_conflict_info")
    has_conflicts = fields.Boolean(compute="_compute_conflict_info")
    contact_line_ids = fields.One2many(
        "sports.patient.merge.contact.line", "wizard_id",
        string="Other matching contacts",
    )
    blocked_contact_info = fields.Html(
        string="Cannot be merged here", compute="_compute_blocked_contact_info")
    has_blocked_contacts = fields.Boolean(
        compute="_compute_blocked_contact_info")

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids")
        if active_ids is None:
            # Created programmatically rather than opened from the Players
            # list; there is nothing to seed. action_merge still validates.
            return res
        patients = self.env["sports.patient"].browse(active_ids).exists()
        if len(patients) < 2:
            raise UserError(_(
                "Select at least two players to merge."))
        res["patient_ids"] = [Command.set(patients.ids)]
        # Default to the oldest record: most likely the original, and the one
        # other records were duplicated from.
        res["dst_patient_id"] = min(patients.ids)
        res["contact_line_ids"] = [
            Command.create(vals) for vals in self._candidate_line_vals(patients)
        ]
        return res

    # ------------------------------------------------------------------
    # Matching contacts
    # ------------------------------------------------------------------
    @api.model
    def _match_domain(self, patients):
        """Exact email OR sanitised phone OR same last name.

        Sanitised phone matters: the real duplicate pair carried
        '514-555-0142' and '+1 514-555-0142'. Exact string matching finds
        nothing. Blank email/phone are excluded -- with false == false
        matching, one merge could sweep in every contact lacking an email.
        """
        partners = patients.partner_id
        emails = [e for e in partners.mapped("email") if e]
        phones = [p for p in partners.mapped("phone_sanitized") if p]
        last_names = [n for n in patients.mapped("last_name") if n]

        leaves = []
        if emails:
            leaves.append([("email", "in", emails)])
        if phones:
            leaves.append([("phone_sanitized", "in", phones)])
        for last_name in set(last_names):
            leaves.append([("name", "ilike", last_name)])
        if not leaves:
            return None
        domain = leaves[0]
        for leaf in leaves[1:]:
            domain = ["|"] + domain + leaf
        return domain

    @api.model
    def _candidate_line_vals(self, patients):
        domain = self._match_domain(patients)
        if not domain:
            return []
        # One query, not one per patient. Archived partners are excluded by the
        # default active_test.
        candidates = self.env["res.partner"].search(domain) - patients.partner_id
        if not candidates:
            return []
        # A partner belonging to ANOTHER patient must never be offered here:
        # folding it into the res.partner merge would smuggle a second patient
        # past the contact-merge guard and re-create the deletion bug.
        others = self.env["sports.patient"].sudo().with_context(
            active_test=False,
        ).search([("partner_id", "in", candidates.ids)])
        blocked = others.partner_id

        vals = []
        for partner in candidates - blocked:
            vals.append({
                "partner_id": partner.id,
                "match_reason": self._match_reason(partner, patients),
            })
        for partner in blocked:
            patient = others.filtered(lambda p: p.partner_id == partner)[:1]
            vals.append({
                "partner_id": partner.id,
                "match_reason": self._match_reason(partner, patients),
                "blocked_patient_id": patient.id,
            })
        return vals

    @api.model
    def _match_reason(self, partner, patients):
        partners = patients.partner_id
        if partner.email and partner.email in partners.mapped("email"):
            return _("Same email")
        if (partner.phone_sanitized
                and partner.phone_sanitized in partners.mapped("phone_sanitized")):
            return _("Same phone")
        return _("Same last name")

    @api.depends("contact_line_ids.blocked_patient_id")
    def _compute_blocked_contact_info(self):
        for wizard in self:
            blocked = wizard.contact_line_ids.filtered("blocked_patient_id")
            wizard.has_blocked_contacts = bool(blocked)
            if not blocked:
                wizard.blocked_contact_info = False
                continue
            rows = Markup("").join(
                Markup("<li>%s &mdash; belongs to player <b>%s</b></li>") % (
                    line.partner_id.display_name,
                    line.blocked_patient_id.display_name,
                )
                for line in blocked
            )
            wizard.blocked_contact_info = Markup(
                "<p>These contacts look like duplicates, but each belongs to "
                "another player, so they cannot be merged here:</p>"
                "<ul>%s</ul>"
                "<p>If any of them is really the same person, cancel and "
                "include that player in this merge instead.</p>"
            ) % rows

    # ------------------------------------------------------------------
    # Conflicts
    # ------------------------------------------------------------------
    @api.depends("patient_ids", "dst_patient_id")
    def _compute_conflict_info(self):
        for wizard in self:
            conflicts = wizard._collect_conflicts()
            wizard.has_conflicts = bool(conflicts)
            if not conflicts:
                wizard.conflict_info = False
                continue
            # Free text and scalars need different wording. Saying "discarding"
            # about a field that is actually concatenated is simply false, and
            # a blanket footnote contradicting the per-field line is worse than
            # no warning at all.
            rows = Markup("")
            for conflict in conflicts:
                if conflict["combined"]:
                    rows += Markup(
                        "<li><b>%s</b>: the players disagree &mdash; both values "
                        "are kept and combined, nothing is lost. Please reconcile "
                        "them on the surviving player afterwards.</li>"
                    ) % conflict["label"]
                else:
                    rows += Markup(
                        "<li><b>%s</b>: keeping &ldquo;%s&rdquo;, discarding "
                        "&ldquo;%s&rdquo; (from %s)</li>"
                    ) % (conflict["label"], conflict["dst"], conflict["src"],
                         conflict["src_patient"])
            body = Markup("<p>These fields differ between the players:</p><ul>%s</ul>") % rows
            if any(not c["combined"] for c in conflicts):
                body += Markup(
                    "<p>Discarded values are replaced by <b>%s</b>&rsquo;s. If a "
                    "discarded value is the right one, cancel, fix it on the "
                    "player&rsquo;s form, and merge again.</p>"
                ) % wizard.dst_patient_id.display_name
            wizard.conflict_info = body

    def _collect_conflicts(self):
        """Fields set on BOTH the destination and a source, with differing
        values. A source-only value is not a conflict -- it fills a blank.

        Only fields the acting user can actually READ are compared:
        date_of_birth, team_info_notes and allergies are group-restricted, and
        a restricted value must not leak into a warning.
        """
        self.ensure_one()
        dst = self.dst_patient_id
        srcs = self.patient_ids - dst
        if not dst or not srcs:
            return []
        readable = self.env["sports.patient"].fields_get(
            allfields=list(CONFLICT_FIELDS))
        conflicts = []
        for fname in CONFLICT_FIELDS:
            if fname not in readable:
                continue
            dst_value = dst[fname]
            if not dst_value:
                continue
            for src in srcs:
                src_value = src[fname]
                if src_value and src_value != dst_value:
                    conflicts.append({
                        "label": readable[fname]["string"],
                        "dst": dst_value,
                        "src": src_value,
                        "src_patient": src.display_name,
                        # Free text is concatenated, not overwritten -- the
                        # warning must not claim the source value is discarded.
                        "combined": fname in TEXT_FIELDS,
                    })
        return conflicts

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------
    def action_merge(self):
        self.ensure_one()
        dst = self.dst_patient_id
        if len(self.patient_ids) < 2:
            raise UserError(_("Select at least two players to merge."))
        if dst not in self.patient_ids:
            raise UserError(_(
                "The player to keep must be one of the players being merged."))
        if not self.env.user.has_group(
                "bemade_sports_clinic.group_sports_clinic_admin"):
            raise UserError(_(
                "Only Sports Clinic Administrators can merge players."))
        anonymized = self.patient_ids.sudo().filtered("is_anonymized")
        if anonymized:
            raise UserError(_(
                "These players have been anonymized under Law 25 and cannot be "
                "merged: %(names)s\n\nTheir identifying data was erased on "
                "purpose; merging one would relink erased data to an "
                "identified person.",
                names=", ".join(anonymized.mapped("display_name")),
            ))

        dst = dst.sudo()
        srcs = (self.patient_ids - self.dst_patient_id).sudo()

        values = self._resolve_values(dst, srcs)
        self._reassign_children(dst, srcs)
        if values:
            dst.with_context(**QUIET).write(values)
        self._move_chatter(dst, srcs)

        audit_body = self._audit_body(dst, srcs)
        src_partners = srcs.partner_id
        # Children have moved; unlinking now cannot cascade a clinical record.
        srcs.unlink()
        # _message_log, not message_post: it records the note without notifying
        # followers. message_post on mt_note would email the whole team about a
        # merge of historical data.
        dst.with_context(**QUIET)._message_log(body=audit_body)

        # Belt and braces: a blocked line is not tickable in the view, but if one
        # is selected anyway its partner belongs to another player, and merging
        # it would put two patients into the contact merge -- the exact shape of
        # the bug this whole change exists to prevent. Refuse explicitly rather
        # than relying on the guard to catch it downstream.
        selected = self.contact_line_ids.filtered("selected")
        smuggled = selected.filtered("blocked_patient_id")
        if smuggled:
            raise UserError(_(
                "These contacts belong to other players and cannot be merged "
                "here: %(names)s\n\nInclude those players in the merge instead.",
                names=", ".join(smuggled.mapped("partner_id.display_name")),
            ))

        # Only one patient remains, so the contact-merge guard passes on its own.
        partners = dst.partner_id | src_partners | selected.partner_id
        if len(partners) > 1:
            self.env["base.partner.merge.automatic.wizard"].sudo()._merge(
                partners.ids, dst_partner=dst.partner_id)
        return {"type": "ir.actions.act_window_close"}

    def _resolve_values(self, dst, srcs):
        values = {}
        for fname in SCALAR_FIELDS:
            if not dst[fname]:
                for src in srcs:
                    if src[fname]:
                        values[fname] = src[fname]
                        break
        # Law 25 retention clock: the most recent consultation across all the
        # merged records, NOT the destination's. Taking a stale destination
        # value could prematurely age out a record seen more recently.
        dates = [p.last_consultation_date
                 for p in (dst | srcs) if p.last_consultation_date]
        if dates and max(dates) != dst.last_consultation_date:
            values["last_consultation_date"] = max(dates)
        teams = dst.team_ids | srcs.team_ids
        if teams != dst.team_ids:
            values["team_ids"] = [Command.set(teams.ids)]
        for fname in TEXT_FIELDS:
            merged = self._merge_text(dst, srcs, fname)
            if merged != dst[fname]:
                values[fname] = merged
        # match_status/practice_status are deliberately absent: only four
        # combinations are valid (see constrain_match_and_practice_status), so
        # they stay as the destination's pair rather than being resolved
        # independently into an invalid one.
        return values

    def _merge_text(self, dst, srcs, fname):
        """Destination text first, each differing source appended under a
        provenance header. Identical text is not duplicated."""
        parts = []
        seen = set()
        for patient in dst | srcs:
            value = (patient[fname] or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            if patient == dst:
                parts.append(value)
            else:
                parts.append("--- %s ---\n%s" % (
                    _("Merged from %(name)s (ID %(id)s)",
                      name=patient.display_name, id=patient.id),
                    value,
                ))
        return "\n\n".join(parts) if parts else False

    def _reassign_children(self, dst, srcs):
        """Injuries FIRST: sports.treatment.note._check_injury_patient_match and
        sports.injury.document._check_injury_belongs_to_patient both assert
        injury.patient_id == record.patient_id, so moving a note before its
        injury raises."""
        for model in ("sports.patient.injury", "sports.treatment.note",
                      "sports.injury.document", "sports.patient.contact"):
            records = self.env[model].sudo().with_context(
                active_test=False).search([("patient_id", "in", srcs.ids)])
            if records:
                records.with_context(**QUIET).write({"patient_id": dst.id})

    def _move_chatter(self, dst, srcs):
        messages = self.env["mail.message"].sudo().search([
            ("model", "=", "sports.patient"), ("res_id", "in", srcs.ids),
        ])
        if messages:
            messages.write({"res_id": dst.id})
        activities = self.env["mail.activity"].sudo().search([
            ("res_model", "=", "sports.patient"), ("res_id", "in", srcs.ids),
        ])
        if activities:
            activities.write({"res_id": dst.id})
        followers = self.env["mail.followers"].sudo().search([
            ("res_model", "=", "sports.patient"), ("res_id", "in", srcs.ids),
        ])
        existing = dst.sudo().message_follower_ids.mapped("partner_id")
        for follower in followers:
            if follower.partner_id in existing:
                follower.unlink()
            else:
                follower.write({"res_id": dst.id})
                existing |= follower.partner_id

    def _audit_body(self, dst, srcs):
        # Must be Markup: mail bodies escape plain strings, so a str here shows
        # the user raw <p> tags in the chatter. Markup %-interpolation also
        # escapes the values, which matters because player names are user input.
        rows = Markup("").join(
            Markup("<li>%s (ID %s)</li>") % (src.display_name, src.id)
            for src in srcs
        )
        # Name the acting user explicitly: the merge runs sudo, so the message
        # author would otherwise be the system user and the Law 25 trail would
        # not record who did this.
        return Markup(_(
            "<p>Merged into this player by %(user)s:</p><ul>%(rows)s</ul>"
            "<p>Their injuries, treatment notes, documents, team links and "
            "history were moved here. Notes and allergies from the merged "
            "records were combined into this one &mdash; please review them.</p>"
        )) % {
            "user": self.env.user.display_name,
            "rows": rows,
        }


class PatientMergeContactLine(models.TransientModel):
    _name = "sports.patient.merge.contact.line"
    _description = "Merge Players: Matching Contact"

    wizard_id = fields.Many2one(
        "sports.patient.merge.wizard", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", string="Contact", readonly=True)
    match_reason = fields.Char(string="Matched on", readonly=True)
    selected = fields.Boolean(string="Merge too", default=False)
    blocked_patient_id = fields.Many2one(
        "sports.patient", string="Belongs to player", readonly=True)
    partner_email = fields.Char(related="partner_id.email", readonly=True)
    partner_phone = fields.Char(related="partner_id.phone", readonly=True)
