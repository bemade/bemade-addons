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
            # Task 1727: a « Retour prévu » row adds
            'min': 'YYYY-MM-DD',           # today: its date input's min
            'needs_date': bool,            # the proposed date has passed —
            'hint': str,                   # pick a new one (why, shown on the row)
            # Task 1670: a SELECTION row (match / practice status) adds
            'type': 'selection',           # (absent = a date row)
            'options': [{'value', 'label'}, ...],  # the field's choices
        }, ...],
    }

The builders compute as sudo (they are only called for a therapist, after an
access-checked save) and format in the caller's language.
"""
from datetime import timedelta

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
        item = {
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
        if record._name == 'sports.patient' and field == 'predicted_return_date':
            # Task 1727: « Retour prévu » is never set in the past — the row's
            # date input starts at today; a proposed date that has already
            # passed asks for a new one (an empty, editable date + the reason)
            # instead of failing on « Apply ».
            today = fields.Date.context_today(self)
            item['min'] = fields.Date.to_string(today)
            if proposed and fields.Date.to_date(proposed) < today:
                item.update({
                    'proposed': '',
                    'editable': True,
                    'needs_date': True,
                    'hint': self.env._("The proposed date (%s) has passed: pick a new date, today or later.",
                                       self._sc_proposal_date_display(proposed)),
                })
        return item

    def _sc_proposal_selection_item(self, record, field, label, current, proposed,
                                    tickable=True, checked=True):
        """Task 1670: a row proposing a SELECTION value (match / practice
        status), editable among the field's own choices (request language)."""
        labels = dict(record._fields[field]._description_selection(self.env))
        return {
            'model': record._name,
            'id': record.id,
            'field': field,
            'label': str(label),
            'type': 'selection',
            'current': current or '',
            'proposed': proposed or '',
            'current_display': labels.get(current, '—') if current else '—',
            'proposed_display': labels.get(proposed, '—') if proposed else '—',
            'options': [{'value': value, 'label': str(text)} for value, text in labels.items()],
            'editable': True,
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
        return date to the resolution date (editable) — and (task 1670)
        Match / Practice back to « Yes » when they differ (each editable
        among the field's choices; the pair rule is checked on apply). None
        otherwise."""
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
        # Task 1670 (owner default): Match : Oui / Pratique : Oui.
        statuses = [
            self._sc_proposal_selection_item(self, field, label, patient[field], 'yes')
            for field, label in (('match_status', env._("Match")), ('practice_status', env._("Practice")))
            if patient[field] != 'yes'
        ]
        if statuses:
            message = env._("This was the player's last active injury. Clear the predicted return, "
                            "set the actual return date and reset their statuses?")
        else:
            message = env._("This was the player's last active injury. Clear the predicted return "
                            "and set the actual return date?")
        return self._sc_proposal('last_resolved', env._("No active injury left"), message, items + statuses)

    def _after_injury_moved_back(self, injury, previous):
        """Task 1631 (owner decision 2026-10-20): ``injury`` was moved BACK
        from ``previous`` (a correction from the card's status pill):
        propose undoing the dates that followed the previous status — each
        row ticked, untickable, dates editable:

        * from « resolved »: clear the injury's resolution date; clear the
          player's actual return when it is that resolution date;
        * back to « active » from « resolved »: restore the predicted
          resolution date the resolve wiped (mail tracking; an empty
          editable date when there is none) and set Retour prévu to the
          latest predicted date of the active injuries, this one included;
        * back to « unverified »: Retour prévu recomputed from the
          remaining active injuries (cleared when none is left).

        The ONLY proposal of a backward move (the forward builders are not
        called). None when nothing applies."""
        self.ensure_one()
        injury = injury.sudo()
        patient = self.sudo()
        env = self.env
        items = []
        resolution = injury.resolution_date
        if previous == 'resolved' and resolution:
            items.append(self._sc_proposal_item(
                injury, 'resolution_date', env._("Resolution Date"), resolution, False))
        restored = False
        if previous == 'resolved' and injury.stage == 'active' and not injury.predicted_resolution_date:
            restored = injury._sc_predicted_before_resolve()
            # Review 2026-10-20 (#1631): never propose a past (or no) date —
            # a week from today, editable in the popup.
            today = fields.Date.context_today(self)
            if not restored or restored < today:
                restored = today + timedelta(days=7)
            items.append(self._sc_proposal_item(
                injury, 'predicted_resolution_date', env._("Predicted Resolution Date"),
                False, restored, editable=True))
        if previous == 'resolved' and resolution and patient.return_date == resolution:
            items.append(self._sc_proposal_item(
                self, 'return_date', env._("Actual return date"), patient.return_date, False))
        current = patient.predicted_return_date
        if injury.stage == 'active':
            dates = [d for d in self._sc_active_injuries().mapped('predicted_resolution_date') if d]
            if restored:
                dates.append(restored)
            latest = max(dates) if dates else False
            if latest and latest != current:
                items.append(self._sc_proposal_item(
                    self, 'predicted_return_date', env._("Predicted return"),
                    current, latest, editable=True))
        else:
            latest = self._sc_latest_active_predicted()
            if not self._sc_active_injuries():
                latest = False
                propose = bool(current)
            else:
                propose = bool(latest) and latest != current
            if propose:
                items.append(self._sc_proposal_item(
                    self, 'predicted_return_date', env._("Predicted return"),
                    current, latest, editable=True))
        labels = dict(injury._fields['stage']._description_selection(env))
        return self._sc_proposal(
            'moved_back',
            env._("Correct the dates?"),
            env._("The injury was moved back to %s. These dates followed the previous status: "
                  "untick the ones to keep.", labels.get(injury.stage, injury.stage)),
            items,
        )
