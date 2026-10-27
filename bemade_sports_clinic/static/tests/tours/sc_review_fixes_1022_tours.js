/*
 * Owner review fixes 2026-10-22 (tests/test_review_fixes_1022.py), phone
 * 390 px and laptop 1366 px. Synthetic data; triggers language-independent
 * (the reason texts are read from the panel's own data-* strings).
 *
 * - sc_1022_player_add_list / sc_1022_player_add_team (#1655): « Create » is
 *   greyed with its reason (missing fields, a half-filled emergency
 *   contact, an exact twin), enables once valid; an invalid emergency
 *   mobile is refused BY THE SERVER inside the panel: message under the
 *   field, panel open, values kept, no page change. The team variant starts
 *   on the team's dashboard and opens the Joueurs tab client-side (the
 *   owner's phone bounce).
 * (sc_1022_medical_undo went with the « None known » undo, task 1677.)
 *
 * Real taps / the toast's place inside the popup on a phone stay
 * UNVERIFIED here — the dev-review click-through covers them.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const PANEL = "details.o_sc_player_add[open] form[data-sc-player-add]";
const SUBMIT = `${PANEL} [data-sc-player-add-submit]`;

function q(selector) {
    return document.querySelector(selector);
}

function type(selector, value) {
    const el = q(selector);
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

function texts() {
    return q(`${PANEL} [data-sc-player-add-reasons]`).dataset;
}

function reason() {
    const line = q(`${PANEL} [data-sc-player-add-reason]`);
    return line.hidden ? "" : line.textContent.trim();
}

function panelSteps() {
    return [
        {
            content: "Greyed, the reason lists every missing field",
            trigger: `${SUBMIT}[aria-disabled="true"]`,
            run() {
                window.__sc1022NoReload = true;
                const t = texts();
                const line = q(`${PANEL} [data-sc-player-add-reason]`);
                assert(this.anchor.getAttribute("aria-describedby") === line.id, "aria-describedby");
                assert(reason() === `${t.missing} ${t.first}, ${t.last}, ${t.dob}`, `reason: ${reason()}`);
                type(`${PANEL} [data-sc-player-add-field="first"]`, "Pat");
                type(`${PANEL} [data-sc-player-add-field="last"]`, "One");
            },
        },
        {
            content: "Only the date of birth is missing",
            trigger: `${PANEL} [data-sc-check-results][data-sc-ready="1"]`,
            run() {
                const t = texts();
                assert(reason() === `${t.missing} ${t.dob}`, `reason: ${reason()}`);
                type(`${PANEL} [data-sc-player-add-field="dob"]`, "2009-04-05");
            },
        },
        {
            content: "An exact twin: still greyed, says so",
            trigger: `${PANEL} [data-sc-check-results][data-sc-exact="1"]`,
            run() {
                assert(q(SUBMIT).getAttribute("aria-disabled") === "true", "Create enabled on a twin");
                assert(reason() === texts().exact, `reason: ${reason()}`);
                // A click does nothing but say why.
                q(SUBMIT).click();
                type(`${PANEL} [data-sc-player-add-field="first"]`, "Tourist");
                type(`${PANEL} [data-sc-player-add-field="last"]`, "Synthetic");
                type(`${PANEL} [data-sc-player-add-field="dob"]`, "2012-03-04");
            },
        },
        {
            content: "A new name: enabled, no reason",
            trigger: `${PANEL} [data-sc-check-none]`,
            run() {
                assert(q(SUBMIT).getAttribute("aria-disabled") === "false", "Create still greyed");
                assert(reason() === "", `reason: ${reason()}`);
                q(`${PANEL} details[data-sc-player-add-ec-box]`).open = true;
                type(`${PANEL} [data-sc-player-add-ec="name"]`, "Synthetic Parent");
            },
        },
        {
            content: "A half-filled emergency contact: greyed again",
            trigger: `${SUBMIT}[aria-disabled="true"]`,
            run() {
                assert(reason() === texts().ec, `reason: ${reason()}`);
                type(`${PANEL} [data-sc-player-add-ec="mobile"]`, "555-0100");
            },
        },
        {
            content: "Complete: « Create »",
            trigger: `${SUBMIT}[aria-disabled="false"]`,
            run: "click",
        },
        {
            content: "The server refuses the mobile: under the field, panel open, values kept",
            trigger: `${PANEL} [data-sc-player-add-field-error="ec_mobile"]`,
            run() {
                assert(window.__sc1022NoReload, "the page changed");
                assert(q(`${PANEL} [data-sc-player-add-field="first"]`).value === "Tourist", "first name lost");
                assert(q(`${PANEL} [data-sc-player-add-ec="mobile"]`).value === "555-0100", "mobile lost");
                assert(q(`${PANEL} [data-sc-player-add-ec="mobile"]`).getAttribute("aria-invalid") === "true",
                    "aria-invalid");
                assert(!window.location.search.includes("tab=dashboard"), "back on the dashboard");
            },
        },
    ];
}

tours.add("sc_1022_player_add_list", { steps: panelSteps });

tours.add("sc_1022_player_add_team", {
    steps: () => [
        {
            content: "The team's dashboard: open the Joueurs tab",
            trigger: '[data-sc-tabs] a[data-sc-tab="players"]',
            run: "click",
        },
        {
            content: "« + Add »",
            trigger: 'button.o_sc_list_add[aria-controls="sc_add_player"]',
            run: "click",
        },
        ...panelSteps(),
    ],
});
