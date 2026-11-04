/*
 * Task 1747 — Clinique: « Seen » on a worklist row opens that player's file
 * (as the legacy screen's redirect did); « Arrived » stays in place, and so
 * does « Seen » on a row the user may not open
 * (tests/test_clinic_seen_opens_file_1747.py, laptop + phone).
 * Starts with player A selected (laptop: A's file beside the list; phone:
 * the list tab); rows are found by their name.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const LIST = '[data-sc-section="clinic.worklist"]';
const PANE = '[data-sc-section="clinic.dossier"]';

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function row(name) {
    return `${LIST} li.o_sc_wl_row:contains("${name}")`;
}

function patientParam() {
    return new URLSearchParams(window.location.search).get("patient");
}

tours.add("sc_1747_seen_opens_file", {
    steps: () => [
        {
            content: "Player A is selected; mark the page (a navigation drops it)",
            trigger: `${LIST} .o_sc_wl_live li.o_sc_wl_row`,
            run() {
                window.__sc1747Page = patientParam();
                assert(window.__sc1747Page, "no patient in the URL");
            },
        },
        {
            content: "« Arrived » on player B",
            trigger: `${row("Bravo")} button[data-sc-wl-state="arrived"]`,
            run: "click",
        },
        {
            content: "B arrived, saved; same page, same file",
            trigger: `${row("Bravo")} button[data-sc-wl-state="arrived"][aria-pressed="true"]`,
            async run() {
                await new Promise((resolve) => setTimeout(resolve, 500));
                assert(window.__sc1747Page, "« Arrived » navigated");
                assert(patientParam() === window.__sc1747Page, "the file changed");
            },
        },
        {
            content: "« Seen » on a row the user may not open (no link)",
            trigger: `${row("Closed")} button[data-sc-wl-state="seen"]`,
            run: "click",
        },
        {
            content: "Seen, saved; still the same page",
            trigger: `${row("Closed")} button[data-sc-wl-state="seen"][aria-pressed="true"]`,
            async run() {
                await new Promise((resolve) => setTimeout(resolve, 500));
                assert(window.__sc1747Page, "« Seen » without a file navigated");
                assert(patientParam() === window.__sc1747Page, "the file changed");
            },
        },
        {
            content: "« Seen » on player B",
            trigger: `${row("Bravo")} button[data-sc-wl-state="seen"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "B's file opened (a new page, B in the URL and the pane)",
            trigger: `${PANE} [data-sc-section="clinic.dossier.player"] .o_sc_player_row:contains("Bravo")`,
            run() {
                assert(!window.__sc1747Page, "no navigation");
                assert(patientParam() === this.anchor.dataset.scPlayerId, `URL patient ${patientParam()}`);
                assert(
                    document.querySelector(`${LIST} li[data-sc-patient-id="${patientParam()}"][data-sc-state="seen"]`),
                    "B is not seen"
                );
            },
        },
    ],
});
