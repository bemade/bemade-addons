/*
 * Task 1753 — the player header keeps its status and medical pills visible
 * while the card is edited (tests/test_hero_pills_edit_mode_1753.py).
 * Language-independent triggers, synthetic fixtures.
 *
 * - sc_1753_hero_pills_edit (therapist, player page, starts « yes:yes »):
 *   open the header pencil — the Match / Practice and medical pills stay
 *   visible; Match -> no from the edit mode recolours the pill in place
 *   (edit mode kept, no reload, pills not duplicated); ✓ closes the edit
 *   mode, the read view shows with the pills once.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const HERO = '[data-pk-section="player.hero"]';
const STATUS = `${HERO} > [data-pk-section="player.status"]`;
const MEDICAL = `${STATUS} [data-pk-section="player.medical"]`;
const EDIT = `${HERO} > [data-pk-edit-view="edit"]`;
const READ = `${HERO} > [data-pk-edit-view="read"]`;
const PENCIL = `${HERO} button[data-pk-edit-toggle]`;

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function visible(selector) {
    const el = document.querySelector(selector);
    return Boolean(el && el.getClientRects().length);
}

function toggle(key, tone) {
    return `${STATUS} [data-pk-pill-select][data-pk-pill-key="${key}"]:not([aria-busy]) button.o_pk_pill_select.o_pk_chip_${tone}`;
}

function assertOnce() {
    assert(document.querySelectorAll('[data-pk-section="player.status"]').length === 1, "status block duplicated");
    assert(document.querySelectorAll('[data-pk-section="player.status.readonly"]').length === 1, "status pills duplicated");
    assert(document.querySelectorAll(`${HERO} [data-pk-section="player.medical"]`).length === 1, "medical pills duplicated");
    assert(document.querySelectorAll(`${STATUS} [data-pk-pill-key="match"]`).length === 1, "match pill duplicated");
}

tours.add("sc_1753_hero_pills_edit", {
    steps: () => [
        {
            content: "Read mode: pills shown; open the header pencil",
            trigger: `${PENCIL}[aria-expanded="false"]`,
            run() {
                window.__sc1753NoReload = true;
                assert(visible(toggle("match", "green")), "match pill not shown in read mode");
                assert(visible(`${MEDICAL} button[data-sc-med-pill="allergy"]`), "allergy pill not shown in read mode");
                this.anchor.click();
            },
        },
        {
            content: "Edit mode: the read view is hidden, the pills stay visible",
            trigger: `${EDIT}:not([hidden])`,
            run() {
                assert(document.querySelector(READ).hidden, "the read view is still shown");
                assert(visible(toggle("match", "green")), "match pill hidden in edit mode");
                assert(visible(toggle("practice", "green")), "practice pill hidden in edit mode");
                assert(visible(`${MEDICAL} button[data-sc-med-pill="allergy"]`), "allergy pill hidden in edit mode");
                assert(visible(`${MEDICAL} button[data-sc-med-pill="medical_alert"]`), "medical alert pill hidden in edit mode");
                assertOnce();
            },
        },
        {
            content: "Open the Match pill from the edit mode",
            trigger: toggle("match", "green"),
            run: "click",
        },
        {
            content: "Pick no",
            trigger: `${STATUS} [data-pk-pill-key="match"] [role="menuitemradio"][data-pk-pill-value="no"]:not([aria-disabled])`,
            run: "click",
        },
        {
            content: "Match red in place; still in edit mode, no reload, no duplicate",
            trigger: toggle("match", "red"),
            run() {
                assert(window.__sc1753NoReload, "the page reloaded");
                assert(!document.querySelector(EDIT).hidden, "the edit mode closed");
                assert(document.querySelector(READ).hidden, "the read view came back");
                assert(visible(toggle("practice", "green")), "practice changed or hidden");
                assertOnce();
            },
        },
        {
            content: "Close the edit mode (✓)",
            trigger: `${PENCIL}[aria-expanded="true"]`,
            run: "click",
        },
        {
            content: "Read view back, pills shown once, Match still red",
            trigger: `${READ}:not([hidden])`,
            run() {
                assert(window.__sc1753NoReload, "the page reloaded");
                assert(document.querySelector(EDIT).hidden, "the edit mode is still open");
                assert(visible(toggle("match", "red")), "match pill not red in read mode");
                assert(visible(`${MEDICAL} button[data-sc-med-pill="allergy"]`), "allergy pill lost");
                assertOnce();
            },
        },
    ],
});
