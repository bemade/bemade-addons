from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['sports.team'].search([])._allow_access_for_staff_internal_users()
    cr.execute('CREATE EXTENSION IF NOT EXISTS "unaccent"')
