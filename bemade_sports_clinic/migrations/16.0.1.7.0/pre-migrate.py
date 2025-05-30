import openupgradelib.openupgrade as ou
from odoo import SUPERUSER_ID, api

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ou.delete_records_safely_by_xml_id(env, [
        "bemade_sports_clinic.restrict_team_access_to_allowed_internal_users",
        "bemade_sports_clinic.restrict_patient_access_to_allowed_internal_users",
        "bemade_sports_clinic.restrict_injury_access_to_allowed_internal_users",
    ])