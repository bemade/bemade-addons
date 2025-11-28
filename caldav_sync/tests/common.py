from odoo import Command


class CaldavTestCommon:
    @classmethod
    def _generate_user(
        cls, name, caldav_username=None, caldav_password=None, caldav_url=None
    ):
        groups_ids = cls.env.ref("base.group_user") | cls.env.ref(
            "base.group_partner_manager"
        )
        vals = {
            "name": name,
            "login": name,
            "password": name,
            "email": name + "@example.com",
            "groups_id": [Command.set(groups_ids.ids)],
        }
        if caldav_username:
            vals.update(caldav_username=caldav_username)
        if caldav_password:
            vals.update(caldav_password=caldav_password)
        if caldav_url:
            vals.update(caldav_calendar_url=caldav_url)
        user = cls.env["res.users"].create(vals)
        return user
