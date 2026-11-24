from odoo import api, models


class MailRenderMixin(models.AbstractModel):
    _inherit = "mail.render.mixin"

    @api.model
    def _render_template(
        self, template_src, model, res_ids, engine="inline_template", add_context=None, options=None
    ):
        """Show the signature email address in the signatures a template embeds.

        Templates insert a user's stored signature verbatim (``user.signature``,
        ``object.user_id.signature``, ``object.write_uid.signature``...). Each
        copy of the signature of a user with a signature email address is
        replaced by its outgoing version, before the link post-processing
        (which would make the copy differ from the stored signature). The rest
        of the rendered body is not touched.
        """
        options = dict(options or {})
        post_process = options.pop("post_process", False)
        rendered = super()._render_template(
            template_src, model, res_ids, engine=engine, add_context=add_context, options=options
        )
        if model and rendered and any(value and "@" in value for value in rendered.values()):
            rendered = self._mail_signature_rewrite_rendered(model, rendered)
        if post_process:
            rendered = self._render_template_postprocess(model, rendered)
        return rendered

    @api.model
    def _mail_signature_rewrite_rendered(self, model, rendered):
        Users = self.env["res.users"].sudo()
        with_setting = Users.search([("mail_send_as_alias_id", "!=", False)])
        user_fields = [
            name
            for name, field in self.env[model]._fields.items()
            if field.type == "many2one" and field.comodel_name == "res.users"
        ]
        result = {}
        for res_id, value in rendered.items():
            if not value or "@" not in value:
                result[res_id] = value
                continue
            record = self.env[model].browse(res_id).exists() if res_id else self.env[model]
            users = with_setting | self.env.user.sudo()
            for name in user_fields:
                users |= record.sudo()[name] if record else Users
            users = users.filtered(lambda u: not u.share and u.signature)
            result[res_id] = Users._mail_signature_rewrite_html(value, users, record or None)
        return result
