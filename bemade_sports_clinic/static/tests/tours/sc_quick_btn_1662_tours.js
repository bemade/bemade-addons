/*
 * Task 1662 — the injury card's quick « Vérifier » / « Résoudre » button is
 * as tall as the status pill on its row, and nothing on the row overlaps
 * (tests/test_quick_btn_height_tours_1662.py: phone 390 px and laptop).
 *
 * Real phone rendering stays UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function intersects(a, b) {
    const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
    const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    return x > 0.5 && y > 0.5;
}

function checkRow(quick) {
    const summary = quick.closest("summary");
    assert(summary, "the quick button is not in a card summary");
    const pill = summary.querySelector(".o_sc_pill_select, .o_sc_status_pill");
    assert(pill, "no status pill on the row");
    const qh = quick.getBoundingClientRect().height;
    const ph = pill.getBoundingClientRect().height;
    assert(Math.abs(qh - ph) <= 1, `quick button ${qh}px vs status pill ${ph}px`);
    // Every pill / chip / control of the row: pairwise no overlap.
    const items = [...summary.querySelectorAll(
        ".o_sc_quick_btn, .o_sc_pill_select_wrap, .o_sc_status_pill:not(.o_sc_pill_select), .o_sc_chip, .o_sc_activity_clock, .o_sc_row_trailing > .o_sc_icon"
    )].filter((el) => el.getClientRects().length);
    for (let i = 0; i < items.length; i++) {
        for (let j = i + 1; j < items.length; j++) {
            if (items[i].contains(items[j]) || items[j].contains(items[i])) {
                continue;
            }
            assert(!intersects(items[i].getBoundingClientRect(), items[j].getBoundingClientRect()),
                `overlap: ${items[i].className} / ${items[j].className}`);
        }
    }
    // The row's content stays inside the card (no overflow to the right).
    const row = summary.getBoundingClientRect();
    for (const el of items) {
        assert(el.getBoundingClientRect().right <= row.right + 1, `${el.className} overflows the row`);
    }
}

tours.add("sc_1662_quick_btn_height", {
    steps: () => [
        {
            content: "Résoudre (active injury with chips) and Vérifier (unverified)",
            trigger: '[data-sc-injury-quick="resolve"]',
            run() {
                const resolve = document.querySelectorAll('[data-sc-injury-quick="resolve"]');
                const verify = document.querySelectorAll('[data-sc-injury-quick="verify"]');
                assert(resolve.length && verify.length, "both quick buttons expected");
                const chips = resolve[0].closest("summary").querySelectorAll(".o_sc_chip");
                assert(chips.length >= 2, "the active injury should carry its two chips");
                [...resolve, ...verify].forEach(checkRow);
            },
        },
    ],
});
