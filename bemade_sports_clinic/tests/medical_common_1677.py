"""Task 1677 — shared helper of the medical tests (no test methods: imported
by the test modules only). Synthetic fixtures only (this repository is
public)."""


def set_medical(player, allergies=(), conditions=(), epipen=None, epipen_note=None,
                none_allergy=None, none_condition=None):
    """Put ``player``'s medical lists in a given state, as the superuser and
    without notes: ``allergies`` = [(name, life_threatening)], ``conditions``
    = [(name, life_threatening[, first_aid_note])] — REPLACING the lists;
    the other keys only when given. The levels follow (computed)."""
    player = player.sudo()
    Item = player.env['sports.patient.critical.item'].sudo().with_context(sc_critical_quiet=True)
    Item.search([('patient_id', '=', player.id)]).unlink()
    vals_list = [{'patient_id': player.id, 'family': 'allergy', 'name': name,
                  'life_threatening': vital} for name, vital in allergies]
    for row in conditions:
        name, vital = row[0], row[1]
        vals_list.append({'patient_id': player.id, 'family': 'medical_alert', 'name': name,
                          'life_threatening': vital, 'first_aid_note': row[2] if len(row) > 2 else False})
    if vals_list:
        Item.create(vals_list)
    vals = {}
    if epipen is not None:
        vals['allergy_epipen'] = epipen
    elif not player.allergy_epipen_state:
        # Task 1717: allergies wait for the EpiPen answer — a fixture with
        # allergies answers it (« no ») unless it says otherwise.
        vals['allergy_epipen_state'] = 'no'
    if epipen_note is not None:
        vals['allergy_epipen_note'] = epipen_note
    if none_allergy is not None:
        vals['allergy_none_confirmed'] = none_allergy
    if none_condition is not None:
        vals['medical_none_confirmed'] = none_condition
    if vals:
        player.write(vals)
    player.invalidate_recordset()
    return player
