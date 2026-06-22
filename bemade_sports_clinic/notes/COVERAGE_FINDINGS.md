# Test coverage pass — findings (2026-06-21 → 22 overnight)

Orchestrated overnight run to lift `bemade_sports_clinic` test coverage and
incorporate the orphaned (unregistered) test files. What landed and what remains.

## Done

### Orphaned test files registered + repaired for 19.0
Eight previously-unregistered `test_*.py` files were added to `tests/__init__.py`.
Six of them errored in `setUpClass` (all on the removed model `sports.organization`)
and were repaired for the 19.0 API. Common drifts fixed:
- `sports.organization` (removed) → `res.partner` with `is_company=True`.
- `sports.team.organization_id` → `parent_id`.
- `sports.patient.birthdate` → `date_of_birth`.
- `sports.team.staff.user_id` (gone) → linkage via `partner_id` (`user_ids` is related/readonly).
- `invalidate_cache()` → `invalidate_recordset()`.
- HttpCase `self.csrf_token()` dropped in 19.0 → harvest token from a rendered form.
- Renamed portal routes: `/my/player/injury` → `/my/injury/edit`, `/my/patient/injury/update` → `/my/injury/save`.
- `sports.patient.contact`: `relationship`/`phone` → `contact_type`/`mobile`.
- `treatment_professional_ids` is m2m to `res.users` (link the user, not the partner).

Now green and registered: `test_e2e_workflows`, `test_injury_assignment`,
`test_injury_notifications`, `test_treatment_notes`, plus the passing methods of
`test_security_integration`, `test_portal_integration`, `test_portal_injury_form`,
`test_player_availability`.

### Real source bug found + fixed
`controllers/patient_injury_portal.py` — `edit_injury_form` (and the new-injury
form) searched `res.users` by `('all_group_ids', 'in', [...])`, which reads
`res.groups`. Portal users have no `res.groups` ACL, so **`/my/injury/edit` 403'd
for every portal user** (a regression from the earlier all_group_ids audit fix).
Fixed by `.sudo()`-ing those identity-level searches (same pattern as
`sports.event`). Surfaced by repairing `test_security_integration` (test_01/02).

## Triage of the 5 quarantined tests (2026-06-22) — DONE
Triaging the 5 surfaced **2 real source bugs** (now fixed + tests un-quarantined),
**2 test-drift fixes**, and **1 genuine behaviour gap** (still skipped):

- ✅ **REAL BUG — `test_02_coach_portal_access`** (un-quarantined). The player-detail
  template read the TP-only `allergies` field unconditionally (`sports_clinic_portal_views.xml`
  line ~1232), so **a coach opening any player page got a 403** (`AccessError` on the
  group-restricted field). Fixed: guard with `is_treatment_prof` (mirroring the correct
  guard at line ~1395). Coaches now see the player page (without allergies).
- ✅ **REAL BUG — `test_04_injury_verification_workflow`** (un-quarantined). The portal
  verify route/button is exposed to portal TPs, but `patient_injury.action_verify_injury`
  required the *internal* TP group, so **portal TPs could not verify injuries**. Fixed:
  the model gate now also accepts `group_portal_treatment_professional` (team access is
  still enforced by the controller's `_check_access_to_injury`).
- ✅ **Test drift — `test_therapist_sees_parental_consent_field` + `test_01_therapist_portal_access`**
  (un-quarantined). They asserted the field's *backend* string "Consent for Disclosure to
  Parent", but the portal form hardcodes the label "Parental Consent". Switched to robust
  field-presence assertions (`id="parental_consent"` / `name="parental_consent"`).
- ⏸️ **Still skipped — `test_availability_tracking`.** Confirmed via shell that writing a
  `tracking=True` availability field (real `match_status` yes→no change) produces **no**
  chatter tracking message (only the "Patient created" message remains). This is a genuine
  mail-tracking behaviour gap, not a test fix — needs a product/mail decision (should
  availability changes be audited in the chatter in 19.0?).

## Not reached tonight — recommended next step
Module-wide ≥80% was NOT reached. The overnight window was largely consumed by
the T0 baseline run (~4h, bloated by the erroring orphan HttpCase classes) and
the orphan repairs. The remaining gap is the portal controllers, still low:
`player_management_portal` (~6%), `events_portal` (~13%), `timesheets_portal`
(~10%), `team_management_portal`/`patient_injury_portal` (~23%). These need new
HttpCase tests (see `TEST_COVERAGE_PLAN.md` T1–T8). Note the architectural
constraint discovered: parallel test-validation on a single shared Odoo env is
racy (the tests package imports as a unit), so that push wants either per-agent
isolated envs or a sequential/CI run.
