# Part of Odoo Herd Portal. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class K8sOdooInstance(models.Model):
    """Add client ownership and field-level secrecy to k8s.odoo.instance.

    ``allowed_partner_ids`` links an instance to the commercial partners
    (companies) whose portal users may see it. Entries are normalised to
    commercial partners on write so that any contact of an allowed company
    matches the portal record rule.

    Sensitive fields (raw spec/status JSON, deployment conditions) are
    redefined with ``groups="odoo_herd.group_k8s_user"`` so that portal users
    cannot read them even via the ORM -- defense in depth on top of the record
    rule and ACL.
    """

    _inherit = "k8s.odoo.instance"

    allowed_partner_ids = fields.Many2many(
        "res.partner",
        "k8s_odoo_instance_allowed_partner_rel",
        "instance_id",
        "partner_id",
        string="Allowed Partners",
        help=(
            "Commercial partners (companies) whose portal users may view this "
            "instance. Contacts are normalised to their commercial partner on "
            "write, so any contact of an allowed company matches."
        ),
    )

    # Field-level secrecy: restrict the raw internal blobs to K8s users.
    spec = fields.Text(groups="odoo_herd.group_k8s_user")
    status = fields.Text(groups="odoo_herd.group_k8s_user")
    conditions = fields.Text(groups="odoo_herd.group_k8s_user")

    @api.model
    def _normalise_allowed_partner_commands(self, vals):
        """Rewrite allowed_partner_ids commands to use commercial partners.

        Handles the link/replace forms that carry partner ids (Command.set /
        Command.link / Command.create-by-id). Unlink/clear forms are left
        untouched. Returns ``vals`` (mutated copy) ready to pass to super().
        """
        commands = vals.get("allowed_partner_ids")
        if not commands:
            return vals
        Partner = self.env["res.partner"]
        new_commands = []
        for command in commands:
            # x2many commands are 3-tuples/lists: (code, id, values)
            if isinstance(command, (list, tuple)) and len(command) == 3:
                code = command[0]
                if code in (fields.Command.SET, fields.Command.LINK):
                    if code == fields.Command.SET:
                        ids = command[2] or []
                    else:
                        ids = [command[1]]
                    partners = Partner.browse(ids).exists()
                    commercial = partners.commercial_partner_id
                    if code == fields.Command.SET:
                        new_commands.append(fields.Command.set(commercial.ids))
                    else:
                        for pid in commercial.ids:
                            new_commands.append(fields.Command.link(pid))
                    continue
            new_commands.append(command)
        vals = dict(vals)
        vals["allowed_partner_ids"] = new_commands
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            self._normalise_allowed_partner_commands(vals) for vals in vals_list
        ]
        return super().create(vals_list)

    def write(self, vals):
        if "allowed_partner_ids" in vals:
            vals = self._normalise_allowed_partner_commands(vals)
        return super().write(vals)
