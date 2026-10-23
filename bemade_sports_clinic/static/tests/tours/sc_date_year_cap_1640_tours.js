/*
 * Task 1640 — date inputs carry the 4-digit-year bounds
 * (tests/test_date_year_cap_1640.py).
 *
 * sc_1640_team: a seeded « 202610-10-10 » announcement deadline draft is
 * dropped on load (not restored); the OWL « Valide jusqu'au » input and the
 * plain QWeb « add player » DOB input carry min / max; inputs injected later
 * (a fragment swap, a lazy body, a focus) are stamped; an existing bound is
 * never overridden.
 * sc_1640_player: the player page's autosave date inputs carry the bounds.
 *
 * Chrome's year-segment auto-advance itself is NOT observable headless —
 * UNVERIFIED until the /dev-review real-keyboard check.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const MIN = "1900-01-01";
const MAX = "9999-12-31";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function draftKey(recordKey) {
    const app = document.querySelector(".o_sc_app[data-sc-uid]");
    return `sc_draft:${app.dataset.scDb || ""}:${app.dataset.scUid}:${recordKey}`;
}

function teamId() {
    return new URLSearchParams(window.location.search).get("team_id");
}

function assertBounds(input, label, min = MIN, max = MAX) {
    assert(input, `${label}: input missing`);
    assert(input.getAttribute("min") === min, `${label}: min=${input.getAttribute("min")}`);
    assert(input.getAttribute("max") === max, `${label}: max=${input.getAttribute("max")}`);
}

tours.add("sc_1640_team", {
    steps: () => [
        {
            content: "Seed a bad deadline draft (6-digit year), then reload",
            trigger: ".o_sc_app[data-sc-uid]",
            run() {
                window.localStorage.setItem(
                    draftKey(`sports.team.${teamId()}.announcement_deadline`),
                    JSON.stringify({ value: "202610-10-10", at: Date.now() })
                );
                window.location.reload();
            },
            expectUnloadPage: true,
        },
        {
            content: "Open the compose form (the announcement card's pencil)",
            trigger: '[data-sc-edit-card="announcement"] button[data-sc-edit-toggle]',
            run: "click",
        },
        {
            content: "The bad draft is not restored, and is gone",
            trigger: "#sc_team_announcement_deadline",
            run() {
                const input = document.querySelector("#sc_team_announcement_deadline");
                assert(input.value === "", `restored value: ${input.value}`);
                assert(
                    window.localStorage.getItem(
                        draftKey(`sports.team.${teamId()}.announcement_deadline`)
                    ) === null,
                    "the bad draft was kept"
                );
                assert(!document.querySelector(".o_sc_draft_banner"), "« Brouillon restauré » shown");
                assertBounds(input, "Valide jusqu'au (OWL)");
            },
        },
        {
            content: "The plain QWeb « add player » DOB input is stamped (on load)",
            trigger: "main#sc_content",
            run() {
                // Task 1655: the inline create panel's date of birth.
                assertBounds(document.querySelector('#sc_add_player [data-sc-player-add-field="dob"]'), "add-player DOB (QWeb)");
            },
        },
        {
            content: "Injected inputs: a fragment swap, a lazy body, a focus; existing bounds kept",
            trigger: "main#sc_content",
            run() {
                const main = document.querySelector("main#sc_content");
                const box = document.createElement("div");
                box.innerHTML =
                    '<input type="date" id="t1640_frag"/>' +
                    '<input type="date" id="t1640_today" max="2026-01-01"/>' +
                    '<input type="datetime-local" id="t1640_dt"/>';
                main.appendChild(box);
                document.dispatchEvent(new CustomEvent("sc:fragments"));
                assertBounds(document.querySelector("#t1640_frag"), "fragment input");
                assertBounds(document.querySelector("#t1640_today"), "own max kept", MIN, "2026-01-01");
                assertBounds(
                    document.querySelector("#t1640_dt"),
                    "datetime-local",
                    "1900-01-01T00:00",
                    "9999-12-31T23:59"
                );

                const lazy = document.createElement("div");
                main.appendChild(lazy);
                lazy.innerHTML = '<input type="date" id="t1640_lazy" min="2026-10-22"/>';
                lazy.dispatchEvent(new CustomEvent("sc:lazy-loaded", { bubbles: true }));
                assertBounds(document.querySelector("#t1640_lazy"), "lazy input (own min kept)", "2026-10-22", MAX);

                const late = document.createElement("input");
                late.type = "date";
                late.id = "t1640_late";
                main.appendChild(late);
                assert(!late.hasAttribute("max"), "stamped before any trigger?");
                late.focus();
                assertBounds(late, "focus safety net");
                box.remove();
                lazy.remove();
                late.remove();
            },
        },
    ],
});

tours.add("sc_1640_player", {
    steps: () => [
        {
            content: "The player's autosave date inputs carry the bounds",
            trigger: 'main#sc_content:has(.o_sc_autosave input[type="date"])',
            run() {
                const inputs = [...document.querySelectorAll('.o_sc_autosave input[type="date"]')];
                assert(inputs.length >= 1, "no autosave date input");
                for (const input of inputs) {
                    assertBounds(input, `autosave ${input.id || input.name}`);
                }
            },
        },
    ],
});
