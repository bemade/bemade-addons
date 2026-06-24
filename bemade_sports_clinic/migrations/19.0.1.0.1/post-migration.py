"""Re-enable views that the Odoo 18.0 → 19.0 upgrade pipeline disabled.

The upgrade service deactivates any custom view whose XML it can't
re-validate (typically because the view referenced a field that was
renamed/removed in 19). When this module's 19 sources are then loaded
with ``-u``, the new ``arch_db`` is written but ``active`` is a
separate field — not in our XML — so it stays ``False`` from the
upgrade-time deactivation.

This script flips the four views back on by xml_id, idempotently.
Pure no-op on fresh 19 installs (where ``active`` is already True).
"""
import logging

_logger = logging.getLogger(__name__)

# xml_id (within bemade_sports_clinic) -> human label, just for logging
_VIEWS_TO_REENABLE = {
    "sports_team_view_form": "sports.team form",
    "sports_team_staff_view_form": "sports.team.staff form",
    "sports_patient_view_search": "sports.patient search",
    "sports_patient_view_form": "sports.patient form",
}


def migrate(cr, version):
    if not version:
        # First-time install — views were just created with active=True.
        return

    from odoo.api import Environment, SUPERUSER_ID  # noqa: PLC0415

    env = Environment(cr, SUPERUSER_ID, {})
    for xml_id, label in _VIEWS_TO_REENABLE.items():
        view = env.ref(f"bemade_sports_clinic.{xml_id}", raise_if_not_found=False)
        if view and not view.active:
            view.active = True
            _logger.info("Re-enabled %s view (id=%s)", label, view.id)
