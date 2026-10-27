/*
 * Task 1729 — the player header's edit rows on a phone: no overlapping
 * controls (tests/test_header_edit_phone_tours_1729.py, 360 / 390 px and a
 * 1366 px laptop). Synthetic data; language-independent triggers.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

const HERO = '[data-sc-section="player.hero"]';
const EDIT = '[data-sc-section="player.header.edit"]';
const TRAINING = '[data-sc-section="player.training.edit"]';
const ROWS = [TRAINING, '[data-sc-section="player.predicted_return"]', '[data-sc-section="player.return_date.edit"]'];
const CONTROLS = 'button, a[href], input:not([type="hidden"]), textarea, select';

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function visible(el) {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && !el.closest("[hidden], .visually-hidden")
        && getComputedStyle(el).visibility !== "hidden";
}

function describe(el) {
    return `${el.tagName.toLowerCase()}.${[...el.classList].join(".")} «${(el.textContent || el.value || "").trim().slice(0, 24)}»`;
}

function overlaps(root) {
    const els = [...root.querySelectorAll(CONTROLS)].filter(visible);
    const out = [];
    for (let i = 0; i < els.length; i++) {
        for (let j = i + 1; j < els.length; j++) {
            if (els[i].contains(els[j]) || els[j].contains(els[i])) {
                continue;
            }
            const a = els[i].getBoundingClientRect();
            const b = els[j].getBoundingClientRect();
            const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
            const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
            if (w > 0.5 && h > 0.5) {
                out.push(`${describe(els[i])} × ${describe(els[j])}`);
            }
        }
    }
    return out;
}

function typeAndLeave(input, value) {
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.blur();
    input.dispatchEvent(new FocusEvent("blur")); // headless CI: blur() fires no event without window focus
}

const openPencil = {
    content: "Open the header's pencil",
    trigger: `${HERO} > button[data-sc-edit-toggle][aria-expanded="false"]`,
    run: "click",
};

const everyClear = {
    content: "Every row shows its « Effacer »",
    trigger: `${EDIT}:not([hidden]) ${TRAINING} .o_sc_clear_btn`,
    run() {
        for (const row of ROWS) {
            assert(document.querySelector(`${row} .o_sc_clear_btn`), `no Effacer in ${row}`);
        }
    },
};

const pastDate = {
    content: "Type a past « Retour prévu » (refused inline, #1727)",
    trigger: '[data-sc-section="player.predicted_return"] input[type="date"]',
    run() {
        typeAndLeave(this.anchor, "2001-01-01");
    },
};

tours.add("sc_1729_header_edit_phone", {
    steps: () => [
        openPencil,
        everyClear,
        pastDate,
        {
            content: "No overlap, no overflow; fields full width, actions under them",
            trigger: '[data-sc-section="player.predicted_return"] .o_sc_field_error',
            run() {
                const hero = document.querySelector(HERO);
                const found = overlaps(hero);
                assert(!found.length, `overlapping controls: ${found.join(" | ")}`);
                assert(
                    document.documentElement.scrollWidth <= window.innerWidth,
                    `page wider than the screen: ${document.documentElement.scrollWidth} > ${window.innerWidth}`
                );
                const heroBox = hero.getBoundingClientRect();
                for (const row of ROWS) {
                    const field = document.querySelector(`${row} .o_sc_autosave`);
                    const input = field.querySelector("textarea, input:not([type=hidden])");
                    const clear = field.querySelector(".o_sc_clear_btn");
                    const f = field.getBoundingClientRect();
                    const i = input.getBoundingClientRect();
                    const c = clear.getBoundingClientRect();
                    assert(i.width >= f.width - 2, `${row}: input ${i.width} narrower than its row ${f.width}`);
                    assert(c.top >= i.bottom - 0.5, `${row}: « Effacer » not under its field`);
                    assert(c.right <= heroBox.right + 0.5 && c.left >= heroBox.left - 0.5, `${row}: « Effacer » off the card`);
                }
            },
        },
    ],
});

tours.add("sc_1729_header_edit_laptop", {
    steps: () => [
        openPencil,
        everyClear,
        pastDate,
        {
            content: "Laptop: nothing overlaps; « Effacer » stays on the training title's line",
            trigger: '[data-sc-section="player.predicted_return"] .o_sc_field_error',
            run() {
                const found = overlaps(document.querySelector(HERO));
                assert(!found.length, `overlapping controls: ${found.join(" | ")}`);
                const title = document.querySelector(`${TRAINING} .o_sc_training_title`).getBoundingClientRect();
                const clear = document.querySelector(`${TRAINING} .o_sc_clear_btn`).getBoundingClientRect();
                assert(clear.top < title.bottom && clear.bottom > title.top, "« Effacer » left the title line");
            },
        },
    ],
});
