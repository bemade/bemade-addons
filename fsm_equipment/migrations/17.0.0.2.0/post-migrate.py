from odoo import SUPERUSER_ID, api, Command
from odoo.tools.sql import SQL
import logging


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    sql = "select * from fsm_equipment_component"
    cr.execute(SQL(sql))
    components = cr.dictfetchall()
    sql = "select * from fsm_equipment_component_purpose"
    cr.execute(SQL(sql))
    purposes = cr.dictfetchall()

    env = api.Environment(cr, SUPERUSER_ID, {})

    env["fsm.equipment"].create(
        [
            {
                "name": component["name"],
                "sequence": component["sequence"],
                "parent_id": component["equipment_id"],
                "description": component["note"],
                "product_id": component["product_id"],
            }
            for component in components
        ]
    )
