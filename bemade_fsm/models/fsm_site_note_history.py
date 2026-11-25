from odoo import api, fields, models


class FsmSiteNoteHistory(models.Model):
    """Append-only audit trail of a site's note (``res.partner.fsm_site_note``).

    One row is created by server code (the ``res.partner`` create/write hooks)
    every time the note actually changes, whatever the path: the contact form,
    the close-out wizard or the « Update site note » button on a visit. Rows
    are never edited or deleted from the UI: the model is read-only for every
    group, creation only happens through ``sudo()`` in the hooks and in the
    upgrade seed (pattern of ``sports.injury.note.history``).
    """

    _name = "fsm.site.note.history"
    _description = "Site note history"
    _order = "note_datetime desc, id desc"

    partner_id = fields.Many2one(
        "res.partner",
        string="Site",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=True,
    )
    note_datetime = fields.Datetime(
        string="Date",
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    author_id = fields.Many2one(
        "res.users",
        string="Author",
        default=lambda self: self.env.user,
        readonly=True,
    )
    content = fields.Text(string="Note", readonly=True)
    task_id = fields.Many2one(
        "project.task",
        string="Visit",
        ondelete="set null",
        readonly=True,
        help="The field service task the note was updated from, if any.",
    )

    @api.model
    def _seed_from_current_notes(self):
        """Start the history from the current text: one row per site with a
        non-empty note and no history yet (upgrade to 19.0.0.10.0).

        Dated at the partner's last write; credited to the author of the last
        tracked change of the note when it is known, else to OdooBot. Returns
        the number of rows created. Idempotent."""
        self.env.flush_all()
        root_uid = self.env.ref("base.user_root").id
        self.env.cr.execute(
            """
            WITH last_change AS (
                SELECT DISTINCT ON (m.res_id)
                       m.res_id AS partner_id, u.id AS user_id
                  FROM mail_tracking_value tv
                  JOIN ir_model_fields f ON f.id = tv.field_id
                  JOIN mail_message m ON m.id = tv.mail_message_id
                  LEFT JOIN res_users u ON u.partner_id = m.author_id
                 WHERE f.model = 'res.partner'
                   AND f.name = 'fsm_site_note'
                   AND m.model = 'res.partner'
              ORDER BY m.res_id, m.id DESC, u.id
            )
            INSERT INTO fsm_site_note_history
                   (partner_id, note_datetime, author_id, content,
                    create_uid, create_date, write_uid, write_date)
            SELECT p.id, COALESCE(p.write_date, p.create_date, now() at time zone 'UTC'),
                   COALESCE(lc.user_id, %(root)s), p.fsm_site_note,
                   %(root)s, now() at time zone 'UTC', %(root)s, now() at time zone 'UTC'
              FROM res_partner p
         LEFT JOIN last_change lc ON lc.partner_id = p.id
             WHERE COALESCE(btrim(p.fsm_site_note), '') <> ''
               AND NOT EXISTS (
                       SELECT 1 FROM fsm_site_note_history h
                        WHERE h.partner_id = p.id)
            """,
            {"root": root_uid},
        )
        count = self.env.cr.rowcount
        self.invalidate_model()
        return count
