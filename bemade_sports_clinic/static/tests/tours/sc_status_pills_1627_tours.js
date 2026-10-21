/*
 * Task 1627 — status pill dropdowns (tests/test_status_pills_1627.py).
 * Language-independent triggers, synthetic fixtures.
 *
 * - sc_1627_status_pills (therapist, player page, starts « yes:yes »):
 *   the Practice menu greys « no contact » / « no » while Match = yes (a
 *   greyed pick does nothing); Match -> no, then Practice -> no right after
 *   (no 409): the pills recolour red in place and the return line flips to
 *   « Retour prévu », no reload; « Annuler » restores the previous pair;
 *   Match -> yes: both green, « Retour réel ».
 * - sc_1627_status_pills_dossier (therapist, clinic dossier, « yes:yes »):
 *   Match -> no recolours in place (ends « no:yes »).
 * - sc_1627_status_pills_coach: coloured pills, no button, no menu.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const STATUS = '[data-sc-section="player.status"]';

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function noReload() {
    assert(window.__sc1627NoReload, "the page reloaded");
}

/** The pill toggle of ``key`` (match / practice), fresh (not busy). */
function toggle(scope, key, tone = "") {
    return `${scope} [data-sc-pill-select][data-sc-pill-key="${key}"]:not([aria-busy]) button.o_sc_pill_select${
        tone ? `.o_sc_chip_${tone}` : ""
    }`;
}

function item(scope, key, value) {
    return `${scope} [data-sc-pill-key="${key}"] [role="menuitemradio"][data-sc-pill-value="${value}"]`;
}

/** Open the ``key`` pill and pick ``value`` (two clicks). */
function pickSteps(scope, key, value, fromTone) {
    return [
        {
            content: `Open the ${key} pill`,
            trigger: toggle(scope, key, fromTone),
            run: "click",
        },
        {
            content: `Pick ${value}`,
            trigger: `${item(scope, key, value)}:not([aria-disabled])`,
            run: "click",
        },
    ];
}

tours.add("sc_1627_status_pills", {
    steps: () => [
        {
            content: "Read view: both pills green, no stage chip; open Practice",
            trigger: toggle(STATUS, "practice", "green"),
            run() {
                window.__sc1627NoReload = true;
                assert(!document.querySelector("[data-sc-stage-chip]"), "the stage chip is still there");
                assert(document.querySelector(toggle(STATUS, "match", "green")), "match pill not green");
                this.anchor.click();
            },
        },
        {
            content: "Match = yes: « no contact » and « no » greyed, with a hint",
            trigger: `${item(STATUS, "practice", "no")}[aria-disabled="true"]`,
            run() {
                const contact = document.querySelector(item(STATUS, "practice", "no_contact"));
                assert(contact.getAttribute("aria-disabled") === "true", "no contact not greyed");
                for (const el of [contact, this.anchor]) {
                    assert(el.querySelector(".o_sc_pill_hint")?.textContent.trim(), "a greyed choice has no hint");
                }
                this.anchor.click(); // does nothing
            },
        },
        {
            content: "A greyed pick saved nothing; the menu is still open — close it",
            trigger: `${STATUS} [data-sc-pill-key="practice"] button.o_sc_pill_select.o_sc_chip_green[aria-expanded="true"]`,
            run: "click",
        },
        ...pickSteps(STATUS, "match", "no", "green"),
        {
            content: "Match red in place, Practice still green; « Retour prévu »",
            trigger: toggle(STATUS, "match", "red"),
            run() {
                noReload();
                assert(document.querySelector(toggle(STATUS, "practice", "green")), "practice changed");
                assert(
                    document.querySelector('[data-sc-section="player.return"][data-sc-return-kind="predicted"]'),
                    "the return line did not flip to « Retour prévu »"
                );
            },
        },
        // The second change right after: the fresh fragment's values (no 409).
        ...pickSteps(STATUS, "practice", "no", "green"),
        {
            content: "Both red, in place",
            trigger: toggle(STATUS, "practice", "red"),
            run() {
                noReload();
                assert(document.querySelector(toggle(STATUS, "match", "red")), "match not red");
            },
        },
        {
            content: "« Annuler » on the toast",
            trigger: ".o_sc_toast:not([hidden]) button[data-sc-toast-action]",
            run: "click",
        },
        {
            content: "Undone: Practice green again (Match still no)",
            trigger: toggle(STATUS, "practice", "green"),
            run() {
                noReload();
                assert(document.querySelector(toggle(STATUS, "match", "red")), "match not red");
            },
        },
        ...pickSteps(STATUS, "match", "yes", "red"),
        {
            content: "Both green, « Retour réel », no reload",
            trigger: toggle(STATUS, "match", "green"),
            run() {
                noReload();
                assert(document.querySelector(toggle(STATUS, "practice", "green")), "practice not green");
                assert(
                    document.querySelector('[data-sc-section="player.return"][data-sc-return-kind="actual"]'),
                    "the return line did not flip to « Retour réel »"
                );
            },
        },
    ],
});

const DOSSIER = '[data-sc-section="clinic.dossier.status"]';

tours.add("sc_1627_status_pills_dossier", {
    steps: () => [
        {
            content: "Dossier: the pills, no 4-way changer",
            trigger: toggle(DOSSIER, "match", "green"),
            run() {
                window.__sc1627NoReload = true;
                assert(
                    !document.querySelector('.o_sc_autosave[data-sc-field="sc_status"]'),
                    "the 4-way changer is still there"
                );
                this.anchor.click();
            },
        },
        {
            content: "Pick no",
            trigger: `${item(DOSSIER, "match", "no")}:not([aria-disabled])`,
            run: "click",
        },
        {
            content: "Match red in place",
            trigger: toggle(DOSSIER, "match", "red"),
            run() {
                noReload();
                assert(document.querySelector(toggle(DOSSIER, "practice", "green")), "practice changed");
            },
        },
    ],
});

tours.add("sc_1627_status_pills_coach", {
    steps: () => [
        {
            content: "Coach: coloured read-only pills, no button, no menu",
            trigger: `${STATUS} [data-sc-pill-readonly][data-sc-pill-key="match"].o_sc_status_pill`,
            run() {
                assert(document.querySelector(`${STATUS} [data-sc-pill-readonly][data-sc-pill-key="practice"]`), "no practice pill");
                assert(!document.querySelector(`${STATUS} button`), "a button on a coach's pills");
                assert(!document.querySelector("[data-sc-pill-select]"), "a dropdown for a coach");
            },
        },
    ],
});
