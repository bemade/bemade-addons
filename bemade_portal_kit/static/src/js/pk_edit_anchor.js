/*
 * Task 1642 — after an edit, the screen comes back to the top of the block
 * just edited (inert outside .o_sc_app).
 *
 * On a phone several things move the page once the user leaves a field: the
 * keyboard closing (the viewport grows back), the autosave's fragment swap
 * (a notes history one entry longer, a textarea collapsing) and « Terminé »
 * collapsing the injury card. One shared rule for every card edit block
 * ([data-sc-edit-card] — the injury card's Details / Notes / a document,
 * the player's info groups, the medical card…):
 *
 * - the block is remembered when the user LEAVES one of its fields for
 *   something that is not another field (a tap elsewhere, the keyboard's
 *   « done »), when its « Done » ([data-sc-edit-done]) is pressed, or — the
 *   whole card — on the injury card's « Terminé » (sc_injury_card.js calls
 *   anchorEdited(card));
 * - once things settle — after a fragment swap (« sc:fragments »), a
 *   visualViewport resize (the keyboard closing), or a short timeout — the
 *   window scrolls so the block's top sits just below the sticky app bar.
 *   Re-applied on each of those until ANCHOR_MS has passed;
 * - phone width: always; laptop: only when the block's top is out of view;
 * - never against the user: a touch, a wheel, a key or a tap after the
 *   edit drops the pending anchor;
 * - a block replaced by a swap is found again by its id, else by its
 *   edit-card name within its fragment item.
 */

const ANCHOR_MS = 1500;
const SETTLE_MS = 250;
const GAP = 8;
const EDITABLE = 'input:not([type="button"]):not([type="submit"]):not([type="checkbox"]):not([type="radio"]), textarea, select, [contenteditable="true"]';

let pending = null;
let timer = null;
let deadline = null;

function inShell(node) {
    return Boolean(node && node.closest && node.closest(".o_sc_app"));
}

function isEditable(node) {
    return Boolean(node && node.matches && node.matches(EDITABLE));
}

function laptop() {
    return Boolean(window.matchMedia && window.matchMedia("(min-width: 992px)").matches);
}

function keyOf(block) {
    const item = block.closest("[data-sc-fragment-item]");
    return {
        id: block.id || "",
        item: item ? item.dataset.scFragmentItem : "",
        card: block.dataset.scEditCard || "",
    };
}

function resolve() {
    if (!pending) {
        return null;
    }
    if (pending.block.isConnected) {
        return pending.block;
    }
    const { id, item, card } = pending.key;
    if (id) {
        const found = document.getElementById(id);
        if (found) {
            return found;
        }
    }
    const scope = item
        ? [...document.querySelectorAll("[data-sc-fragment-item]")].find((el) => el.dataset.scFragmentItem === item)
        : document;
    if (!scope) {
        return null;
    }
    if (scope !== document && scope.dataset.scEditCard === card) {
        return scope;
    }
    return (
        [...scope.querySelectorAll("[data-sc-edit-card]")].find((el) => el.dataset.scEditCard === card) || null
    );
}

/** The bottom edge of the sticky app bar (0 when there is none). */
function barBottom() {
    const bar = document.querySelector(".o_sc_app .o_sc_appbar");
    return bar ? Math.max(0, bar.getBoundingClientRect().bottom) : 0;
}

/** Scroll the window so ``block``'s top sits just below the app bar. */
export function scrollToBlock(block) {
    if (!block || !block.isConnected) {
        return;
    }
    const top = block.getBoundingClientRect().top;
    const target = barBottom() + GAP;
    const viewport = window.visualViewport ? window.visualViewport.height : window.innerHeight;
    if (laptop() && top >= target - 1 && top < viewport - 48) {
        return; // in view on a laptop: no needless movement
    }
    const delta = top - target;
    if (Math.abs(delta) > 1) {
        window.scrollBy({ top: delta, left: 0, behavior: "instant" });
    }
}

function apply() {
    timer = null;
    if (!pending) {
        return;
    }
    scrollToBlock(resolve());
}

function schedule(ms) {
    if (!pending) {
        return;
    }
    clearTimeout(timer);
    timer = setTimeout(apply, ms);
}

export function cancelAnchor() {
    pending = null;
    clearTimeout(timer);
    clearTimeout(deadline);
    timer = deadline = null;
}

/**
 * Remember ``block`` (a card edit block, or a whole card) as just edited:
 * the screen comes back to its top once the page settles.
 */
export function anchorEdited(block) {
    if (!block || !inShell(block)) {
        return;
    }
    pending = { block, key: keyOf(block) };
    clearTimeout(deadline);
    deadline = setTimeout(cancelAnchor, ANCHOR_MS);
    schedule(SETTLE_MS);
}

/** Test / debug hook: is an anchor pending? */
export function anchorPending() {
    return Boolean(pending);
}

// Leaving a field of a card block for something that is not another field.
document.addEventListener(
    "focusout",
    (ev) => {
        const field = ev.target;
        if (!isEditable(field) || !inShell(field)) {
            return;
        }
        const block = field.closest("[data-sc-edit-card]");
        if (!block || isEditable(ev.relatedTarget)) {
            return;
        }
        anchorEdited(block);
    },
    true
);

// « Done » of a card block (also clicked by the injury card's « Terminé »,
// which then anchors on the whole card).
document.addEventListener("click", (ev) => {
    const done = ev.target.closest && ev.target.closest("[data-sc-edit-done]");
    if (!done || !inShell(done)) {
        return;
    }
    const block = done.closest("[data-sc-edit-card]");
    if (block) {
        anchorEdited(block);
    }
});

// Settling: the fragment swap, the keyboard closing.
document.addEventListener("sc:fragments", () => schedule(50));
if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => schedule(150));
}

// Never against the user: their own gesture after the edit wins.
for (const type of ["touchstart", "wheel", "pointerdown"]) {
    window.addEventListener(type, () => pending && cancelAnchor(), { capture: true, passive: true });
}
window.addEventListener(
    "keydown",
    (ev) => {
        if (pending && !["Shift", "Control", "Alt", "Meta"].includes(ev.key)) {
            cancelAnchor();
        }
    },
    true
);
