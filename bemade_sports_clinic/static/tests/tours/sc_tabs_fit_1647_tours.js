/*
 * Task 1647 — the tab bars fit a phone's width (tests/test_tabs_fit_tours_1647.py).
 *
 * sc_1647_player_phone (390 / 375 px): the player's five tabs and the
 * Activities count pill are within the viewport, the bar does not scroll
 * sideways, the pill comes before the label, « Docs » shows (not
 * « Documents », kept as the title).
 * sc_1647_player_laptop: the full « Documents » shows, the pill still first.
 *
 * The real iPhone stays UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function visible(el) {
    return Boolean(el && el.getClientRects().length && getComputedStyle(el).display !== "none");
}

function checkPill() {
    const pill = document.querySelector('nav[data-sc-tabs] a[data-sc-tab="activities"] .o_sc_tab_badge');
    assert(pill, "no count pill on Activities");
    assert(pill.nextElementSibling && pill.nextElementSibling.classList.contains("o_sc_tab_label"),
        "the pill does not come before the label");
    return pill;
}

tours.add("sc_1647_player_phone", {
    steps: () => [
        {
            content: "Five tabs + the pill fit the width; « Docs »",
            trigger: 'nav[data-sc-tabs] a[data-sc-tab="activities"]',
            run() {
                const nav = document.querySelector("nav[data-sc-tabs]");
                const tabs = [...nav.querySelectorAll("a[data-sc-tab]")];
                assert(tabs.length === 5, `expected 5 tabs, got ${tabs.length}`);
                assert(nav.scrollWidth <= nav.clientWidth + 0.5,
                    `the tab bar scrolls sideways: ${nav.scrollWidth} > ${nav.clientWidth}`);
                for (const tab of tabs) {
                    const rect = tab.getBoundingClientRect();
                    assert(rect.left >= -0.5 && rect.right <= window.innerWidth + 0.5,
                        `${tab.dataset.scTab} out of view: ${rect.left}-${rect.right} / ${window.innerWidth}`);
                }
                const pill = checkPill().getBoundingClientRect();
                assert(pill.right <= window.innerWidth && pill.width > 0, "the pill is out of view");
                const docs = nav.querySelector('a[data-sc-tab="documents"]');
                assert(visible(docs.querySelector(".o_sc_tab_label_short")), "« Docs » not shown");
                assert(!visible(docs.querySelector(".o_sc_tab_label_long")), "« Documents » shown on a phone");
                assert(docs.getAttribute("title") === docs.querySelector(".o_sc_tab_label_long").textContent,
                    "the full label is not the title");
                for (const label of nav.querySelectorAll(".o_sc_tab_label")) {
                    if (visible(label)) {
                        assert(label.scrollWidth <= label.clientWidth + 1, `« ${label.textContent} » is cut`);
                    }
                }
            },
        },
    ],
});

tours.add("sc_1647_player_laptop", {
    steps: () => [
        {
            content: "Laptop: « Documents » in full, the pill before « Activities »",
            trigger: 'nav[data-sc-tabs] a[data-sc-tab="activities"]',
            run() {
                const docs = document.querySelector('nav[data-sc-tabs] a[data-sc-tab="documents"]');
                assert(visible(docs.querySelector(".o_sc_tab_label_long")), "« Documents » hidden on a laptop");
                assert(!visible(docs.querySelector(".o_sc_tab_label_short")), "« Docs » shown on a laptop");
                checkPill();
            },
        },
    ],
});
