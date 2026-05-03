"""Force re-application of clinic record rules.

Both sports_clinic_rules.xml and sports_clinic_portal_rules.xml are
wrapped in <data noupdate="1"> so that admins who tweak the rules in
the UI don't get overwritten on every module upgrade. The downside is
that rule changes shipped in this codebase never reach existing
installs — this is what caused the 887 hidden-from-coaches filter to
silently not apply, and the same wall blocks the portal-TP scope
tightening shipped in 18.0.3.6.1.

This pre-migration flips ir_model_data.noupdate to False for the
specific rule records we want re-applied, so the module data load
that runs immediately after will overwrite the existing rule rows
with the current XML definitions.
"""

import logging

_logger = logging.getLogger(__name__)

RULE_XML_IDS = (
    # Tightened in 18.0.3.6.1: portal therapist scope changed from
    # unrestricted to team-staff-based.
    'portal_medical_professional_patient_access',
    'portal_medical_professional_injury_access',
    'portal_treatment_professional_player_access',
    'portal_treatment_professional_team_access',
    # Touched in 887 (hidden_from_coaches filter) — never applied on
    # existing installs because of the noupdate guard.
    'portal_coach_injury_access',
    'restrict_staff_access_to_team_injuries',
    'tp_internal_team_injury_full_access',
)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = 'bemade_sports_clinic'
           AND model = 'ir.rule'
           AND name = ANY(%s)
        """,
        (list(RULE_XML_IDS),),
    )
    _logger.info(
        "Cleared noupdate on %d clinic ir.rule records to allow this "
        "upgrade to re-apply tightened rule definitions.",
        cr.rowcount,
    )
