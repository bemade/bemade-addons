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
- `treatment_professional_ids` was m2m to `res.users` (link the user, not the partner) —
  removed with `team_id` in #1240; team staff is the treater list.

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
- ✅ **`test_availability_tracking`** (un-quarantined). Initial finding ("no tracking
  message") was a **test-harness artifact**: Odoo 19 finalizes field tracking in a
  `cr.precommit` callback (runs at commit), and a TransactionCase never commits, so the
  assertion ran before tracking fired. Tracking actually **works** — verified in shell that
  a real `match_status` change posts a chatter entry (with the `match_status` tracking
  value) **both** as an internal user AND as a **portal treatment professional** writing
  non-sudo (no chatter-ACL error — the portal-ACL theory does not bite here). `match_status`/
  `practice_status` are player game/practice availability and are correctly `tracking=True`
  (classified "external", so a change also posts the patient status-update notification).
  Fixed the test: subscribe a follower, `flush_all()` + `cr.precommit.run()`, then assert a
  chatter message was posted. **No source change needed.**

## Phase B — wizard coverage (2026-06-22) — DONE
Token-optimized bounded push (see `TEST_COVERAGE_BOUNDED_PLAN.md`). Opus wrote the
tests directly (the A/B concluded Sonnet-delegation isn't worth the spec-handoff
overhead for small one-off wizards). New `test_cov_*` files, verified on a fresh
clone of the migrated `2026-06-21-fitcrew-test19` DB:

- `event_cancel_wizard` (pilot): 34% → 90%.
- `team_role_mass_assign_wizard` (A/B #1): 37% → 98%, 8 tests.
- `event_recurrence_wizard` (A/B #2): 24% → 87%, 9 tests. Lesson: `create()` DOES run
  `default_get()` for missing fields (via `_add_missing_default_values`); if a wizard's
  `default_get` raises without context, create it through `.with_context(active_model=...,
  active_id=...)`.
- `event_vendor_po_wizard` (Phase B): 15% → 94%, 12 tests. Gotcha: a `sports.event.timesheet`
  defaults `coverage_start/end` from its event, so a "zero-duration" timesheet isn't possible
  via create — the "no lines created" path is reached by running the wizard twice (the second
  pass skips already-linked timesheets).
- `base_partner_merge` (Phase B): 22% → 83%, 4 tests. Remaining misses (summable /
  company-dependent / reference-field branches, parent_id exception path) are not worth
  grinding per the plan.

All suites green (0 failed / 0 error).

## Phase C — model coverage (2026-06-22) — DONE
Opus wrote four `test_cov_*` model suites (75 tests total, all green). Standalone
coverage (these suites in isolation — the existing suite's contribution is additive,
so cumulative module coverage is higher):
- `sports_event_timesheet.py`: 92% — defaults/onchanges/time constraints/invoiced guards/computes.
- `patient.py`: 88% — computes, simple actions, removal workflow (request/remove/archive),
  crons, portal-patient private impl, follower recompute.
- `patient_injury.py`: 84% — verify/resolve/view actions, constraints/onchanges, create
  stage logic (admin-active + portal-coach-unverified+team-assign), TP-change write,
  stale-TP cleanup, verification cron.
- `sports_team.py`: 64% standalone — computes, role constraints, role/group helpers,
  allowed_user_ids inverse, portal-access compute, internal/portal group-grant on staff
  create. The deep `_update_all_portal_groups` / `_update_treatment_professional_group`
  portal-branch matrices were left to the existing suite (not re-targeted; would need a
  multi-user/group fixture grid for marginal gain).

One debug cycle: two `create()` tests used `with_user(<non-admin>)` and hit ACLs
(group_sports_clinic_user can't create injuries; an internal TP user can't write
mail.followers during subscription management). Reworked to a portal-coach creator
(suppressed-notification path, no follower writes) + dropped the internal-TP self-assign
test. The TP self-assign branch (patient_injury ~622-623) is left uncovered.

### Latent issues noticed (NOT fixed under the coverage task — flag for follow-up)
- `patient_injury.py` defines `create()` **twice** (lines ~258 and ~583); the second
  shadows the first, so the first create's subscription/message logic (lines ~260-280)
  is dead code and permanently uncoverable. Likely a merge accident worth consolidating.
- `sports_team.py` `action_revoke_portal_access` raises `AccessError` (line ~304) but the
  module only imports `ValidationError` — the no-permission path would raise `NameError`,
  not a clean AccessError. Only triggers for a non-admin/non-system caller.

Next per the plan: reassess cumulative coverage (full-suite run), then decide on the
controller (HttpCase) tail vs locking in the cheap-won number.

## Reassessment — full-suite coverage (2026-06-22)
Full module suite (`--test-tags=/bemade_sports_clinic`) on a migrated-DB clone: **273 tests,
1 failure** (pre-existing — see below). **Source coverage (models + controllers + wizards):
50.7%** (5379 stmts, 2653 missed).

The cheap bucket is now harvested — models and wizards are well covered:
- Models: timesheet 92%, patient 88%, patient_injury 84%, sports_team 74%, treatment_note 96%, etc.
- Wizards: cancel 90%, recurrence 87%, vendor_po 94%, mass_assign 98%, partner_merge 83%.

**The entire remaining gap is the portal controllers** (HttpCase territory):
- player_management_portal 6%, timesheets_portal 12%, events_portal 15%,
  team_management_portal 24%, patient_injury_portal 37%, task_management_portal 41%,
  access_control_mixin 54%, team_staff_portal 72%.
- ~3,000 controller statements, ~2,150 missed. Going from 50.7% → 80% source coverage is
  almost entirely this controller tail — the expensive HttpCase + portal-auth bucket.

## Scoped controller datapoint — team_staff_portal (2026-06-22)
Ran one focused HttpCase suite (`test_cov_team_staff_portal.py`, 8 tests, all green) on the
cheapest/highest-baseline controller to measure the cost of the HttpCase bucket before
committing to the rest. Result: **team_staff_portal 72% → 78% standalone** (+6 pts).

**Cost was disproportionate to the gain, and a big slice of the "missing" lines turned out
to be uncoverable:**
- 2 debug cycles: a plain portal user 403s on `/my` (the clinic home counters need a clinic
  role, so the `_prepare_events_domain` else-branch is unreachable); and the `/my/team`
  "forbidden" test got 200 because the route is **shadowed**.
- `/my/team` is declared by BOTH `team_staff_portal.view_team` and
  `team_management_portal.view_team` — the latter wins, so **`view_team` here (lines
  ~145-173, ~25 lines / 14% of the file) is dead code reachable by no HTTP request.**
- `_prepare_home_portal_values` / `_prepare_events_domain` / `_get_accessible_teams`
  (lines ~47-58, ~88-106) stayed uncovered even when hitting `/my` and `/my/players`
  directly — the merged-controller MRO binds a different sibling's overrides. Effectively
  dead/shadowed here too.
- Remaining misses are exception-only branches (valid input never triggers them).

So this file's realistic coverable ceiling is ~78%; ~28% of it is dead/shadowed and should
be **deleted/consolidated** rather than tested. This is the controller tail in microcosm:
HttpCase setup + route-ownership forensics + slow runs (~2 min each) to move one small,
already-high controller +6 pts, while discovering much of the gap isn't testable surface.
The big controllers (events_portal 661 stmts/15%, player_management 452/6%) are 3–5× larger
at far lower baselines with more routes and more shadowing to untangle each.

**Recommendation:** do NOT chase 80% module coverage through the controllers as-is. First do
a dead-route audit (the shadowed handlers above are likely repeated across the portal
controllers); deleting dead code raises the percentage honestly and shrinks the surface.
Then, if still wanted, test controllers one-at-a-time with a hard per-file cycle cap.

## Controller GET-route coverage pass (2026-06-23)
Focused HttpCase suites for the six remaining portal controllers (shared fixtures in
`tests/portal_cov_common.py`; GET/list/detail routes only — POST form-submits left out).
Full suite: **313 tests, 0 failed / 0 error.** Source coverage (models+controllers+wizards)
**51.4% → 58.5%.** Per-controller (cumulative): events_portal 12→36%, player_management
6→23%, task_management 41→53%, patient_injury 37→42%, timesheets 14→52%, access_control_mixin
55→65%. team_management stayed 24% (the GET routes I hit overlapped existing coverage; its
remaining bulk is POST player-management handlers). Two bugs surfaced — see DEAD_ROUTE_AUDIT.md
(portal_add_player 500; edit_injury plain-user access to verify).

### Pre-existing failure (NOT caused by the coverage work)
`TestSecurityIntegration.test_01_field_level_security_for_therapist` fails on
`assertIn('Internal Notes', injury_response.text)`. Reproduces in isolation. The portal
renders **fr-CA** (the page shows "Notes internes"), so the English-label assertion drifted
after the fr_CA regeneration. Fix pattern is the same as the earlier parental-consent drift
repair: assert on the field id/name (`internal_notes`) or accept either locale, instead of the
English label. Left for the controller-test pass since it's an HttpCase template assertion.

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
