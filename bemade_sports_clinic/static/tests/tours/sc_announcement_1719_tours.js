/*
 * Task 1719 — the compact team announcement: « See more » only on an
 * overflowing text, expands it in place; the pencil of an empty announcement
 * opens the compose form (tests/test_announcement_compact_1719.py).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const AREA = '[data-sc-section="team.announcement.area"]';
const BODY = `${AREA} .o_sc_announcement_body`;
const MORE = `${AREA} button[data-sc-clamp-more]`;

tours.add("sc_1719_see_more", {
    steps: () => [
        {
            content: "A long text: clamped, « See more » shown on the « Until » line",
            trigger: `${MORE}:not([hidden])`,
            run() {
                const body = document.querySelector(BODY);
                assert(body.scrollHeight > body.clientHeight + 1, "the text is not clamped");
                const lines = Math.round(body.clientHeight / parseFloat(getComputedStyle(body).lineHeight));
                assert(lines <= 3, `${lines} lines shown`);
                const meta = document.querySelector(`${AREA} [data-sc-clamp-meta]`);
                assert(!meta.hidden && meta.textContent.includes("2030"), "the « Until » line");
                assert(!document.querySelector(`${AREA} [data-sc-clamp-sep]`).hidden, "no separator");
                const t = document.querySelector(`${AREA} .o_sc_announcement_titleline`).getBoundingClientRect();
                for (const btn of document.querySelectorAll(`${AREA} .o_sc_announcement_titleline .o_sc_icon_btn`)) {
                    const r = btn.getBoundingClientRect();
                    assert(r.width >= 40 && r.height >= 44, `icon target ${r.width}x${r.height}`);
                    assert(Math.abs(r.top + r.height / 2 - (t.top + t.height / 2)) < 4, "the icons are not on the title line");
                }
            },
        },
        {
            content: "« See more »",
            trigger: MORE,
            run: "click",
        },
        {
            content: "Expanded in place; the link is gone",
            trigger: `${BODY}[data-sc-clamp-open]`,
            run() {
                const body = document.querySelector(BODY);
                assert(body.scrollHeight <= body.clientHeight + 1, "still clamped");
                assert(document.querySelector(MORE).hidden, "« See more » still shown");
                assert(document.querySelector(MORE).getAttribute("aria-expanded") === "true", "aria-expanded");
            },
        },
    ],
});

tours.add("sc_1719_short", {
    steps: () => [
        {
            content: "A short text: no « See more », no meta line",
            trigger: `${BODY}[data-sc-clamp-ready]`,
            run() {
                assert(document.querySelector(MORE).hidden, "« See more » shown on a short text");
                assert(document.querySelector(`${AREA} [data-sc-clamp-meta]`).hidden, "an empty meta line shows");
            },
        },
    ],
});

tours.add("sc_1719_empty_pencil", {
    steps: () => [
        {
            content: "Empty: the muted line; the pencil adds one",
            trigger: `${AREA} .o_sc_announcement_empty`,
            run() {
                document.querySelector(`${AREA} button[data-sc-edit-toggle]`).click();
            },
        },
        {
            content: "The compose form opens",
            trigger: `${AREA} [data-sc-section="team.announcement.edit"]:not([hidden]) #sc_team_announcement`,
        },
    ],
});
