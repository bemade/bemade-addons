"""Adversarial review 2026-10-22 — a player's records stay on that player.

The record rules are checked on a record BEFORE a write only: a portal
therapist could take a record of their own player and ``write({'patient_id':
<another team's player>})`` — the rule passed on the old owner, the record
lands on a player they can't open (an injury or an emergency contact
planted on someone else's file).

``sc_check_patient_unchanged`` refuses a CHANGE of ``patient_id`` for anyone
but the superuser: the legitimate re-parenting flows (the Merge Players
wizard, data cleaning merges, migrations) already run as the superuser.
Writing the same player back is not a change.
"""
from odoo import models
from odoo.exceptions import AccessError


def sc_check_patient_unchanged(records, vals, field="patient_id"):
    if field not in vals or records.env.su:
        return
    new = vals[field]
    if isinstance(new, models.BaseModel):
        new = new.id
    new = new or False
    for record in records.sudo():
        if (record[field].id or False) != new:
            raise AccessError(records.env._("This record can't be moved to another player."))
