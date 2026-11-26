from odoo import api, models


class MailRenderMixin(models.AbstractModel):
    _inherit = "mail.render.mixin"

    def _mail_signature_fixed_email_from(self):
        """The fixed sender of the template being rendered (a literal
        address, no placeholder), or False."""
        if len(self) != 1 or self._name not in ("mail.template", "mail.compose.message"):
            return False
        template = self.template_id if self._name == "mail.compose.message" else self
        email_from = (template or self).email_from
        if not email_from or "{" in email_from:
            return False
        return email_from

    @api.model
    def _render_template(
        self, template_src, model, res_ids, engine="inline_template", add_context=None, options=None
    ):
        """Templates printing a user's signature (``user.signature``,
        ``object.user_id.signature``...) print the signature built for the
        record and the template's sender: each verbatim copy of a stored
        signature is swapped for it, before the link post-processing (which
        would make the copy differ from the stored signature). Only users
        under the company signature policy can differ; the rest of the body
        is not touched."""
        options = dict(options or {})
        post_process = options.pop("post_process", False)
        rendered = super()._render_template(
            template_src, model, res_ids, engine=engine, add_context=add_context, options=options
        )
        if (
            model
            and rendered
            and not self.env.context.get("mail_signature_keep_stored")
            and any(value and "@" in str(value) for value in rendered.values())
            and self.env["res.company"].sudo().search_count(
                [("company_signature_enforced", "=", True)], limit=1
            )
        ):
            rendered = self._mail_signature_swap_rendered(model, rendered)
        if post_process:
            rendered = self._render_template_postprocess(model, rendered)
        return rendered

    @api.model
    def _mail_signature_swap_rendered(self, model, rendered):
        Users = self.env["res.users"].sudo()
        email_from = self._mail_signature_fixed_email_from() or None
        user_fields = [
            name
            for name, field in self.env[model]._fields.items()
            if field.type == "many2one" and field.comodel_name == "res.users"
        ]
        result = {}
        for res_id, value in rendered.items():
            if not value or "@" not in str(value):
                result[res_id] = value
                continue
            record = self.env[model].browse(res_id).exists() if res_id else self.env[model]
            users = self.env.user.sudo()
            for name in user_fields:
                users |= record.sudo()[name] if record else Users
            users = users.filtered(lambda u: not u.share and u.signature)
            result[res_id] = Users._mail_signature_swap_printed(
                value, users, record or None, email_from
            )
        return result
