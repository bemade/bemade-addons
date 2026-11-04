/*
 * Task 1641 — the injury card's « Résoudre » button refreshes the card
 * (tests/test_resolve_refresh_tours_1641.py, phone 390 px and laptop).
 *
 * The focus is where a tap leaves it before the sheet opens — on the
 * button (Chrome desktop / Android), or on the card's <summary> (WebKit —
 * Safari and Chrome on iPhone — never focuses a tapped button; the focus
 * goes to the nearest focusable ancestor, the summary). The native dialog
 * gives that focus back when it closes, and a fragment holding the focus is
 * never swapped (the root cause). Then the sheet is confirmed: the card's
 * status pill must read « resolved » and the « Resolve » button must be gone
 * without a reload. Run on a collapsed row and on an open card.
 *
 * A real phone tap-through stays UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const SHEET = "dialog#sc_injury_resolve_sheet";

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

async function waitFor(check, message, timeout = 8000) {
    const start = Date.now();
    while (!check()) {
        if (Date.now() - start > timeout) {
            throw new Error(`timeout: ${message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
}

function card(diagnosis) {
    return [...document.querySelectorAll("details.o_sc_injury_item")].find((node) =>
        node.querySelector("summary").textContent.includes(diagnosis)
    );
}

function pillValue(diagnosis) {
    const node = card(diagnosis);
    const pill = node && node.querySelector("summary [data-sc-pill-value]");
    return pill ? pill.dataset.scPillValue : null;
}

function resolveSteps(diagnosis, { open, focus }) {
    const state = open ? "[open]" : ":not([open])";
    return [
        {
            content: `Focus the ${focus}, then tap « Resolve » on the ${open ? "open card" : "collapsed row"}`,
            trigger: `details.o_sc_injury_item${state} summary button[data-sc-injury-quick=resolve]`,
            run() {
                window.__sc1641NoReload = "1";
                const button = card(diagnosis).querySelector("summary button[data-sc-injury-quick=resolve]");
                const target = focus === "summary" ? card(diagnosis).querySelector("summary") : button;
                target.focus();
                assert(document.activeElement === target, `the ${focus} did not take the focus`);
                button.click();
            },
        },
        {
            content: "Confirm in the sheet",
            trigger: `${SHEET}[open] [data-sc-injury-resolve-confirm]`,
            run() {
                // The confirm button holds the focus when tapped, as on a device.
                this.anchor.focus();
                this.anchor.click();
            },
        },
        {
            content: "The card reads « resolved », its « Resolve » button gone — no reload",
            trigger: ".o_sc_app",
            async run() {
                await waitFor(() => !document.querySelector(`${SHEET}[open]`), "sheet closed");
                await waitFor(
                    () => pillValue(diagnosis) === "resolved",
                    `the card's pill still reads ${pillValue(diagnosis)}`
                );
                assert(
                    !card(diagnosis).querySelector("summary button[data-sc-injury-quick]"),
                    "the « Resolve » button is still shown"
                );
                assert(card(diagnosis).open === open, "the card opened / closed");
                assert(window.__sc1641NoReload === "1", "the page reloaded");
            },
        },
    ];
}

for (const focus of ["button", "summary"]) {
    tours.add(`sc_1641_resolve_row_${focus}`, {
        steps: () => resolveSteps("Synthetic ankle", { open: false, focus }),
    });
    tours.add(`sc_1641_resolve_open_card_${focus}`, {
        steps: () => resolveSteps("Synthetic ankle", { open: true, focus }),
    });
}
