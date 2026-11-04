/*
 * Task 1614 — the team digest history expands each date in place
 * (tests/test_digest_history_tours_1614.py, phone 390 px and laptop 1366 px).
 * Language-independent triggers only (data attributes, classes).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function rgb(value) {
    const m = (value || "").match(/rgba?\(([^)]+)\)/);
    if (!m) {
        return null;
    }
    const [r, g, b, a] = m[1].split(",").map((v) => parseFloat(v));
    return { r, g, b, a: a === undefined ? 1 : a };
}

// The first non-transparent background up the tree.
function background(el) {
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
        const c = rgb(getComputedStyle(node).backgroundColor);
        if (c && c.a > 0) {
            c.at = `${node.tagName}.${node.className}`;
            return c;
        }
    }
    return { r: 255, g: 255, b: 255, a: 1 };
}

function luminance({ r, g, b }) {
    const lin = (v) => {
        v /= 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(el) {
    const fg = luminance(rgb(getComputedStyle(el).color));
    const bg = luminance(background(el));
    return (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
}

const ROW = '[data-sc-section="digest.history"] details[data-sc-digest-row]';

tours.add("sc_1614_digest_history_inline", {
    steps: () => [
        {
            content: "History: the first date (today, with changes) expands in place",
            trigger: `${ROW}:first-child > summary`,
            run: "click",
        },
        {
            content: "The day's body is loaded inside the row, player name readable",
            trigger: `${ROW}[open] .o_sc_lazy_body .team-digest .card-header a`,
            run() {
                const row = document.querySelector(`${ROW}[open]`);
                assert(
                    row.querySelector('.o_sc_lazy_body [data-sc-section="digest.snapshot"]'),
                    "no snapshot line"
                );
                assert(window.location.pathname.endsWith("/digest-history"), "left the list");
                const name = row.querySelector(".o_sc_lazy_body .team-digest .card-header a");
                const ratio = contrast(name);
                assert(ratio >= 3, `player name contrast too low: ${ratio.toFixed(2)}`);
                const detail = row.querySelector("details.o_sc_card_detail");
                assert(detail && !detail.open, "player details are not folded");
                const more = detail.querySelector("summary .o_sc_summary_more");
                assert(
                    contrast(more) >= 3,
                    `« Show details » unreadable: ${getComputedStyle(more).color} on ${JSON.stringify(background(more))}`
                );
            },
        },
        {
            content: "« Show details » unfolds the player's details",
            trigger: `${ROW}[open] details.o_sc_card_detail > summary`,
            run: "click",
        },
        {
            content: "The details are open and readable",
            trigger: `${ROW}[open] details.o_sc_card_detail[open] .o_sc_injury_detail`,
            run() {
                const card = document.querySelector(
                    `${ROW}[open] details.o_sc_card_detail[open] .o_sc_injury_detail`
                );
                assert(contrast(card) >= 3, "injury detail unreadable");
            },
        },
    ],
});
