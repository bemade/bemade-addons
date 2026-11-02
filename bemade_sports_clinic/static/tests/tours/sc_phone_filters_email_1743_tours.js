/*
 * Task 1743 — phone 390 px (tests/test_phone_filters_email_1743.py):
 * the players filters folded in ONE « Filters » disclosure; the event page's
 * email under the name, inside its column. Synthetic data.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const FORM = 'form[data-sc-section="players.search"]';
const FILTERS = `${FORM} details[data-sc-section="players.filters"]`;

tours.add("sc_1743_phone_filters", {
    steps: () => [
        {
            content: "Folded: the names and « Search » in sight, the filters one line",
            trigger: `${FILTERS}:not([open]) > summary`,
            run() {
                const form = document.querySelector(FORM);
                for (const name of ["first_name", "last_name"]) {
                    const box = form.querySelector(`input[name="${name}"]`);
                    assert(box.getBoundingClientRect().height > 0, `${name} hidden`);
                }
                assert(form.querySelector('button[type="submit"]').getBoundingClientRect().height > 0, "no Search");
                        assert(!document.querySelector(`${FILTERS} a[data-sc-action="players.followed"]`).checkVisibility(),
                    "the chip shows while folded");
                assert(this.anchor.getBoundingClientRect().height < 60, "the summary is not one line");
                const doc = document.documentElement;
                assert(doc.scrollWidth <= doc.clientWidth + 1, "horizontal scroll");
                this.anchor.click();
            },
        },
        {
            content: "Open: the « Suivis » chip and « Clear » inside",
            trigger: `${FILTERS}[open] a[data-sc-action="players.followed"]:visible`,
            run() {
                assert(document.querySelector(`${FILTERS} a[data-sc-filter-reset]`).checkVisibility(), "no Clear");
            },
        },
    ],
});

tours.add("sc_1743_event_email", {
    steps: () => [
        {
            content: "The assigned person's email: under the name, inside its column",
            trigger: "[data-sc-event-staff] a[href^='mailto:']",
            run() {
                const link = this.anchor;
                const name = link.parentElement.querySelector("span");
                const dd = link.closest("dd");
                const lr = link.getBoundingClientRect();
                assert(lr.top >= name.getBoundingClientRect().bottom - 1, "the email is not under the name");
                assert(lr.right <= dd.getBoundingClientRect().right + 1, "the email sticks out of its column");
                // At most two lines, split at « @ » (the <wbr>).
                const lines = [...link.getClientRects()].length;
                assert(lines <= 2, `the email takes ${lines} lines`);
                const doc = document.documentElement;
                assert(doc.scrollWidth <= doc.clientWidth + 1, "horizontal scroll");
            },
        },
    ],
});
