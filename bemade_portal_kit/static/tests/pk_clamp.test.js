/*
 * Task 5381 (P4c2) — pk_clamp: a text clamped to N lines
 * ([data-pk-clamp="N"], the kit's CSS) offers « See more » only when it
 * overflows; « See more » / « See less » expand and fold it in place, the
 * « · » separator shows only between two visible meta items. Synthetic
 * fixtures only.
 */
import { describe, expect, getFixture, test } from "@odoo/hoot";

import { setupClamps } from "@bemade_portal_kit/js/pk_clamp";

const LONG = Array.from({ length: 40 }, (_v, i) => `Line ${i} of a long announcement text.`).join(" ");

function mount(text, other = "") {
    // The kit's rule (pk_components.scss; the SCSS is not in the unit test
    // bundle, tests/test_pk_display.py checks it there).
    getFixture().innerHTML = `<style>
        .pk_t_box [data-pk-clamp="3"]:not([data-pk-clamp-open]) {
            display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
        }
    </style><div class="o_pk_app" data-pk-app-shell="1">
        <div class="pk_t_box" style="width: 200px">
            <p class="pk_t_text" data-pk-clamp="3" style="line-height: 20px">${text}</p>
            <div class="pk_t_meta" data-pk-clamp-meta="1">
                ${other}
                <span class="pk_t_sep" data-pk-clamp-sep="1" hidden="">·</span>
                <button type="button" class="pk_t_more" data-pk-clamp-more="1" hidden="" aria-expanded="false">See more</button>
                <button type="button" class="pk_t_less" data-pk-clamp-less="1" hidden="">See less</button>
            </div>
        </div>
    </div>`;
    return getFixture().querySelector(".pk_t_box");
}

describe("pk_clamp", () => {
    test("a long text offers « See more », expands, then folds back with « See less »", () => {
        const box = mount(LONG, '<span class="pk_t_when">Today</span>');
        setupClamps();
        const text = box.querySelector(".pk_t_text");
        const more = box.querySelector(".pk_t_more");
        const less = box.querySelector(".pk_t_less");
        const sep = box.querySelector(".pk_t_sep");
        expect(text.dataset.pkClampReady).toBe("1");
        expect(more.hidden).toBe(false);
        expect(sep.hidden).toBe(false);
        more.click();
        expect(text.dataset.pkClampOpen).toBe("1");
        expect(more.hidden).toBe(true);
        expect(more.getAttribute("aria-expanded")).toBe("true");
        expect(less.hidden).toBe(false);
        expect(sep.hidden).toBe(false);
        expect(text.clientHeight).toBe(text.scrollHeight);
        less.click();
        expect(text.dataset.pkClampOpen).toBe(undefined);
        expect(less.hidden).toBe(true);
        expect(more.hidden).toBe(false);
        expect(more.getAttribute("aria-expanded")).toBe("false");
    });

    test("a short text: no « See more », no separator, the empty meta line hidden", () => {
        const box = mount("Short.");
        setupClamps();
        expect(box.querySelector(".pk_t_more").hidden).toBe(true);
        expect(box.querySelector(".pk_t_sep").hidden).toBe(true);
        expect(box.querySelector(".pk_t_meta").hidden).toBe(true);
    });

    test("without another meta item, no separator", () => {
        const box = mount(LONG);
        setupClamps();
        expect(box.querySelector(".pk_t_more").hidden).toBe(false);
        expect(box.querySelector(".pk_t_sep").hidden).toBe(true);
    });
});
