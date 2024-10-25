from odoo import SUPERUSER_ID, api, Command
from odoo.tools.sql import SQL


def migrate(cr, version):
    sql = "select * from fsm_equipment_component"
    cr.execute(SQL(sql))
    components = cr.dictfetchall()
    sql = "select * from fsm_equipment_component_purpose"
    cr.execute(SQL(sql))
    purposes = cr.dictfetchall()

    env = api.Environment(cr, SUPERUSER_ID, {})
    tags = env["fsm.equipment.tag"].create(
        [{"name": purpose["name"]} for purpose in purposes]
    )

    purpose_dict = {
        purpose["id"]: tags.filtered(lambda tag: tag.name == purpose["name"]).id
        for purpose in purposes
    }

    env["fsm.equipment"].create(
        [
            {
                "name": component["name"],
                "sequence": component["sequence"],
                "tag_ids": [Command.link(purpose_dict[component["purpose_id"]])],
                "parent_id": component["equipment_id"],
                "description": component["note"],
                "product_id": component["product_id"],
            }
            for component in components
        ]
    )
