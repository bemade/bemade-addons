"""Task 1603 — the player's « Retour prévu » (``predicted_return_date``) kept
coherent with the injuries' predicted resolution dates through FOLLOW-UP
PROPOSALS (owner decisions 2026-10-17).

A proposal is a plain, JSON-serializable dict the app shell shows as a sheet
after a save (``propose`` in the save route's answer) — never a blocking
step: the triggering field is already saved. « Apply » posts the ticked
changes to ``/my/app/apply-proposal``, which re-validates them and writes
them through the normal save paths (``SAVE_REGISTRY``)::

    {
        'kind': 'retour_prevu' | 'align_injuries' | 'last_resolved' | …,
        'patient_id': <the player every change belongs to>,
        'title': str, 'message': str,
        'items': [{
            'model', 'id', 'field',        # what « Apply » writes
            'label': str,                  # what the row reads
            'current', 'proposed',         # raw values ('YYYY-MM-DD' / '')
            'current_display', 'proposed_display',
            'editable': bool,              # the proposed date can be changed
            'tickable': bool,              # the row can be unticked
            'checked': bool,               # ticked by default
        }, ...],
    }

The builders compute as sudo (they are only called for a therapist, after an
access-checked save) and format in the caller's language.
"""
from odoo import fields, models
from odoo.tools import format_date


class SportsPatient(models.Model):
    _inherit = 'sports.patient'

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _sc_active_injuries(self):
        """The player's ACTIVE injuries (unverified / resolved ignored)."""
        self.ensure_one()
        return self.sudo().injury_ids.filtered(lambda injury: injury.stage == 'active')

    def _sc_latest_active_predicted(self):
        """The latest predicted resolution date among the active injuries,
        or False when none has one."""
        dates = [d for d in self._sc_active_injuries().mapped('predicted_resolution_date') if d]
        return max(dates) if dates else False

    def _sc_proposal_date_display(self, value):
        return format_date(self.env, value) if value else '—'

    def _sc_proposal_item(self, record, field, label, current, proposed,
                          editable=False, tickable=True, checked=True):
        return {
            'model': record._name,
            'id': record.id,
            'field': field,
            'label': str(label),
            'current': fields.Date.to_string(current) if current else '',
            'proposed': fields.Date.to_string(proposed) if proposed else '',
            'current_display': self._sc_proposal_date_display(current),
            'proposed_display': (self._sc_proposal_date_display(proposed) if proposed
                                 else self.env._("No date")),
            'editable': bool(editable),
            'tickable': bool(tickable),
            'checked': bool(checked),
        }

    def _sc_proposal(self, kind, title, message, items):
        self.ensure_one()
        if not items:
            return None
        return {
            'kind': kind,
            'patient_id': self.id,
            'title': str(title),
            'message': str(message),
            'items': items,
        }

    # ------------------------------------------------------------------
    # the builders
    # ------------------------------------------------------------------
    def _retour_prevu_after_injury_change(self, injury):
        """An ACTIVE injury's predicted resolution date changed (or an
        injury was created / verified with one): propose Retour prévu = the
        latest predicted resolution date among the active injuries, editable
        in the sheet. None when it already matches or nothing applies."""
        self.ensure_one()
        if injury.sudo().stage != 'active':
            return None
        latest = self._sc_latest_active_predicted()
        current = self.sudo().predicted_return_date
        if not latest or latest == current:
            return None
        env = self.env
        return self._sc_proposal(
            'retour_prevu',
            env._("Update the player's predicted return?"),
            env._("The latest predicted resolution date of the player's active injuries is %s.",
                  self._sc_proposal_date_display(latest)),
            [self._sc_proposal_item(self, 'predicted_return_date', env._("Predicted return"),
                                    current, latest, editable=True, tickable=False)],
        )

    def _injuries_alignment_for(self, new_date):
        """Retour prévu was changed by hand to ``new_date``: when it differs
        from the latest active predicted resolution date (earlier OR later),
        propose the new date on each active injury that does not have it —
        each ticked, each untickable. None when cleared or nothing differs."""
        self.ensure_one()
        new_date = fields.Date.to_date(new_date) if new_date else False
        if not new_date:
            return None
        active = self._sc_active_injuries()
        if not active or self._sc_latest_active_predicted() == new_date:
            return None
        env = self.env
        ordered = active.sorted(lambda i: (i.predicted_resolution_date or fields.Date.to_date('1900-01-01'), i.id),
                                reverse=True)
        items = [
            self._sc_proposal_item(
                injury, 'predicted_resolution_date',
                injury.diagnosis or env._("Injury"),
                injury.predicted_resolution_date, new_date)
            for injury in ordered if injury.predicted_resolution_date != new_date
        ]
        return self._sc_proposal(
            'align_injuries',
            env._("Align the injuries' predicted resolution dates?"),
            env._("The predicted return differs from the predicted resolution dates of the "
                  "player's active injuries. Untick the injuries to leave as they are."),
            items,
        )

    def _after_last_active_resolved(self, injury):
        """``injury`` was resolved and the player has no active injury left:
        propose clearing Retour prévu (when set) and setting the actual
        return date to the resolution date (editable). None otherwise."""
        self.ensure_one()
        injury = injury.sudo()
        if injury.stage != 'resolved' or self._sc_active_injuries():
            return None
        patient = self.sudo()
        resolution = injury.resolution_date or fields.Date.context_today(self)
        env = self.env
        items = []
        if patient.predicted_return_date:
            items.append(self._sc_proposal_item(
                self, 'predicted_return_date', env._("Predicted return"),
                patient.predicted_return_date, False))
        if patient.return_date != resolution:
            items.append(self._sc_proposal_item(
                self, 'return_date', env._("Actual return date"),
                patient.return_date, resolution, editable=True))
        return self._sc_proposal(
            'last_resolved',
            env._("No active injury left"),
            env._("This was the player's last active injury. Clear the predicted return "
                  "and set the actual return date?"),
            items,
        )
