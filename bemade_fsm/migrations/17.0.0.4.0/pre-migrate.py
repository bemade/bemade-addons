from odoo import api, SUPERUSER_ID
import logging
from openupgradelib.openupgrade import update_module_moved_models

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """In this version, we separate the bemade_fsm.equipment and its associated models
    out into a new module named fsm_equipment. We need to move those models and rename
    some fields."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("Moving FSM equipment...")
    # Move the old equipment over to the new table
    cr.execute(
        """
    INSERT INTO fsm_equipment
        (id, code, name, description, partner_id, location_notes, active)
    SELECT id, pid_tag code, name, description, partner_location_id, location_notes,
           active
    FROM bemade_fsm_equipment
    """
    )

    _logger.info("Moving FSM equipment tags...")
    # Move the tags
    cr.execute(
        """
    INSERT INTO fsm_equipment_tag (id, name, color)
    SELECT id, name, color FROM bemade_fsm_equipment_tag
    """
    )

    _logger.info("Re-creating equipment to tag relations.")
    # Add the relations
    #  Schema |           Name            | Type | Owner
    # --------+---------------------------------------------------+-------+-------
    #  public | bemade_fsm_equipment_bemade_fsm_equipment_tag_rel | table | odoo
    #  public | bemade_fsm_equipment_sale_order_line_rel     | table | odoo
    #  public | bemade_fsm_equipment_sale_order_rel       | table | odoo
    #  public | bemade_fsm_task_equipment_rel          | table | odoo
    #  public | bemade_fsm_task_template_equipment_rel      | table | odoo
    #  public | fsm_equipment_fsm_equipment_tag_rel       | table | odoo
    #  public | fsm_equipment_sale_order_rel           | table | odoo
    #  public | fsm_task_equipment_rel              | table | odoo

    cr.execute(
        """
    INSERT INTO fsm_task_equipment_rel (equipment_id, task_id)
    SELECT equipment_id, task_id from bemade_fsm_task_equipment_rel
    """
    )

    cr.execute(
        """
        INSERT INTO fsm_equipment_fsm_equipment_tag_rel (fsm_equipment_id, fsm_equipment_tag_id)
        SELECT bemade_fsm_equipment_id, bemade_fsm_equipment_tag_id
            FROM bemade_fsm_equipment_bemade_fsm_equipment_tag_rel
        """
    )

    # Clean up

    _logger.info("Deleting menu items.")
    cr.execute(
        """
        DELETE FROM ir_ui_menu WHERE id in (
            SELECT res_id from ir_model_data where model='ir.ui.menu'
                                               and module='bemade_fsm'
        )
    """
    )

    cr.execute(
        "DELETE FROM ir_model_data where model='ir.ui.menu' and module='bemade_fsm'"
    )

    cr.execute("DELETE FROM ir_model_fields where model ilike 'bemade_fsm.equipment%'")
    cr.execute(
        "DELETE FROM ir_model WHERE name->>'en_US' ilike 'bemade_fsm.equipment%'"
    )
