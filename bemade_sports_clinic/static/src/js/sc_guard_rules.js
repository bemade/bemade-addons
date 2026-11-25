/*
 * Task 5370 (kit P4b): the clinic's own rule of the kit's form guard
 * (@bemade_portal_kit/js/pk_form_guard, registry « pk_guard_rules »).
 *
 *   {"type": "assign", "staff": "assigned_staff_ids", "teams": "team_ids",
 *    "allowed": [team ids], "staff0": "csv", "teams0": "csv", "key": "…"}
 *
 * Review fixes 2026-10-24 (owner policy, the server's
 * sports.event._sc_check_assignment): when the assignees (CSV field
 * ``staff``) differ from ``staff0``, or the teams differ from ``teams0``
 * while there are assignees, every chosen team must be one of ``allowed``
 * (the teams the user staffs).
 */
import { registry } from "@web/core/registry";

function ids(value) {
    return new Set(
        String(value || "")
            .split(",")
            .map((part) => part.trim())
            .filter(Boolean)
    );
}

function same(a, b) {
    return a.size === b.size && [...a].every((item) => b.has(item));
}

registry.category("pk_guard_rules").add("assign", {
    check(rule, ctx) {
        const staff = ids((ctx.named(rule.staff) || {}).value);
        const teams = ids((ctx.named(rule.teams) || {}).value);
        const allowed = new Set((rule.allowed || []).map(String));
        const changed = !same(staff, ids(rule.staff0)) || (staff.size && !same(teams, ids(rule.teams0)));
        return changed && ![...teams].every((team) => allowed.has(team)) ? ctx.message(rule) : "";
    },
});
