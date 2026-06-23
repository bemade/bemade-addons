# Portal controller dead-route / shadowing audit (2026-06-22)

Triggered by the `team_staff_portal` coverage pass, where ~28% of the file stayed
uncovered no matter what HTTP requests were thrown at it. Audited all eight controllers
(AST scan of every `@http.route` path + every method definition, checking super()-chaining)
to separate "genuinely untested" from "untestable because dead/shadowed".

## How routing/merging resolves here
- All portal controllers subclass `CustomerPortal` (+ `AccessControlMixin`) as **siblings**,
  not a chain. Odoo merges same-base controllers into one combined class; a method defined
  in several siblings resolves to **one winner** unless each override calls `super()`.
- Import order in `controllers/__init__.py` decides the winner (later import wins):
  `access_control_mixin → team_staff_portal → patient_injury_portal → team_management_portal
  → player_management_portal → task_management_portal → events_portal → timesheets_portal`.

## Findings

### 1. Route shadowing — `/my/team`  (DEAD: ~40 lines)
`team_staff_portal.view_team` (L142-182) and `team_management_portal.portal_team_players`
(L158) both register `/my/team`. `team_management_portal` is imported later → **its handler
wins**. `view_team`'s only other route, `/my/team/page/<int:page>`, is **referenced nowhere**
(the in-page pager builds `/my/team?team_id=…` query-string URLs, not `/page/N`). So
`view_team` is unreachable in practice. → **Delete `view_team`**; `/my/team` is fully served
by `team_management_portal`.

### 2. Helper shadowing with DIVERGENT logic — events_portal vs team_staff_portal (DEAD: ~35 lines + latent override)
Defined in BOTH controllers, neither calls `super()`, so only **events_portal's** versions
are live (later import):
- `_get_accessible_teams` — events_portal: therapists see **all** teams, coaches see staffed
  teams. team_staff_portal (shadowed): **staff-only for everyone.**
- `_get_organizations` — paired with the above; team_staff_portal's is dead.
- `_prepare_events_domain` — both branch on therapist/coach; team_staff_portal's is dead.

team_staff_portal's `view_players` *calls* `self._get_accessible_teams()` /
`_get_organizations()` for its filter dropdowns — at runtime it gets **events_portal's**
implementations. Net: the "staff-only" team_staff_portal versions never run. This is a
**latent behavioural override**, not just dead code: a therapist on `/my/players` sees the
all-teams filter list (events_portal logic), not the staff-only list the team_staff_portal
author wrote. Confirm which behaviour is intended, then keep one — ideally promoted into
`AccessControlMixin` so it's shared explicitly instead of won-by-import-order.

### 3. Duplicate helper — `_parse_portal_datetime` (DEAD: ~25 lines)
Defined in `events_portal` (L16) and `timesheets_portal` (L12); same purpose, different code,
no super(). `timesheets_portal` wins (later import) → **events_portal's copy is dead.**
Both parse a portal datetime-local string → UTC. → Move one copy into a shared mixin and
delete the other.

## Scope / impact
- **Only `team_staff_portal` is substantially hollowed** (~75 of its 178 statements are
  dead/shadowed: `view_team` + the 3 helpers). It is the oldest controller, since superseded
  by the more specific team/player management controllers. Deleting the dead parts removes
  most of its misleading "missing coverage" and fixes the `_get_accessible_teams` divergence.
- **Every other controller owns its routes uniquely.** Their low coverage
  (events_portal 15%, player_management 6%, timesheets 12%, team_management 24%,
  patient_injury 37%, task_management 41%) is **genuine untested surface, not dead code.**

## Bottom line
The audit does **not** provide a shortcut to 80% — it cleans up ~75 misleading lines in one
controller and surfaces one latent override bug. The rest of the controller tail is real
(expensive HttpCase) work. Recommended cleanup, in order:
1. Delete `team_staff_portal.view_team` (route fully served by `team_management_portal`).
2. Decide the intended `_get_accessible_teams`/`_get_organizations`/`_prepare_events_domain`
   behaviour, keep ONE implementation (promote to `AccessControlMixin`), delete the others.
3. De-duplicate `_parse_portal_datetime` into a shared mixin.
4. (Separately) fix the fr_CA label drift in `TestSecurityIntegration.test_01`.

## Controller GET-route coverage pass (2026-06-23)
Added focused HttpCase suites for the remaining six portal controllers (shared
fixtures in `tests/portal_cov_common.py`), hitting the GET/list/detail routes per
controller (POST form-submit branches deliberately left out — expensive, low ROI).
Two real issues surfaced:

> **FIXED 2026-06-23.** Both issues below are resolved — see the resolution notes inline.

### BUG — `/my/team/<id>/add_player` returns 500 (`portal_add_player` template)
`portal_add_player_form` → `request.render("…portal_add_player", …)` raises
`KeyError: 'user_has_group'` from the template (sports_clinic_portal_views.xml ~L1936).
Notably the **team-detail** template `portal_my_team_players` uses `user_has_group` at
L924/L967 and renders fine — so the helper IS available in that flow but NOT in the
add_player render path. The controller's generic `except` fallback (L152-156) re-renders
with bare `request.params` and also dies on `user_has_group`, so the user gets a 500
instead of a graceful error. Test is `@skip`-marked pending a fix. Likely a 19.0 template
context regression; needs a focused look at why the add_player render lacks the frontend
QWeb globals.
>
> **Root cause / fix:** `user_has_group` is NOT a QWeb global here — `portal_team_players`
> *injects* it into the template context (`'user_has_group': request.env.user.has_group`).
> `portal_add_player_form` rendered the same template family without injecting it, so the
> `t-if="user_has_group(...)"` node raised `KeyError`. The POST sibling
> `portal_add_player_submit` had the **same** defect on ALL its error-render paths
> (invalid/missing/out-of-range DOB, existing-player error, final except) — so any add-player
> validation error 500'd instead of showing the message. Fixed by funneling all six
> `portal_add_player` renders through a single `TeamManagementPortal._render_add_player()`
> helper that guarantees `user_has_group`/`user` in the context. Surfaced by the POST-route
> sampling (`test_cov_team_management_portal_post.py`). Route + all error paths now 200.

### To verify — `/my/injury/edit` opens (200) for an unrelated plain portal user
A plain portal user (no team staff) opening `/my/injury/edit?injury_id=<X>` got 200, not a
403. `base.group_portal` has read on `sports.patient.injury` (ir.model.access), so the
record is readable; whether `edit_injury_form` should hard-gate by team membership for the
*edit* view is worth confirming (mirrors the task-640 record-access concern). Not chased
here; flagged for review. (Note: `portal_team_players` DOES gate correctly — it raises in
`_check_team_access` and redirects to `/my/teams`, returning 200 after the redirect rather
than a 403, which is why a naive status-code assertion misleads.)
>
> **Resolution:** the gate was never missing — `_check_access_to_injury` already denies a
> user with no team-staff relationship. The real defect: `edit_injury_form` (and 10 sibling
> routes in `patient_injury_portal`) rendered the 403 error *template* but never set
> `response.status_code`, so a denied user got an HTTP **200** carrying a Forbidden page —
> i.e. denials reported as success. Fixed by adding `AccessControlMixin._portal_forbidden()`
> (renders the page AND sets status 403) and routing all 11 sites through it. Verified the
> denied user now gets a real 403 with no injury data leaked.
