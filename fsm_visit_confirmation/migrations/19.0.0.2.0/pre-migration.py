# Databases upgraded from 18.0 can hold a "Water Shutdown Required"
# requirement whose ir.model.data entry was lost; reloading the data file
# then crashes on the UNIQUE(name) constraint. Re-bind the xmlid first.


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'fsm_task_client_requirement'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'fsm_visit_confirmation', 'client_requirement_water_shutdown',
               'fsm.task.client.requirement', r.id, false
        FROM fsm_task_client_requirement r
        WHERE r.name->>'en_US' = 'Water Shutdown Required'
          AND NOT EXISTS (
              SELECT 1 FROM ir_model_data
              WHERE module = 'fsm_visit_confirmation'
                AND name = 'client_requirement_water_shutdown'
          )
        ORDER BY r.id
        LIMIT 1
        """
    )
