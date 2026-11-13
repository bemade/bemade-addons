/*
 * The shell's inline edit cards (moved to the kit by task 5381, P4c2).
 * Progressive enhancement, inert outside .o_pk_app.
 *
 * - An edit card ([data-pk-edit-card]) holds a read view
 *   ([data-pk-edit-view="read"]) and an edit view
 *   ([data-pk-edit-view="edit"]). ONE pencil ([data-pk-edit-toggle]) opens
 *   the edit view; while the card is open (data-pk-edit-open) the pencil is
 *   a ✓ (class o_pk_edit_toggle_done, data-pk-edit-toggle-done, its label
 *   from data-pk-edit-done-label on the shell root, else the kit's own) that
 *   closes it like « Done » ([data-pk-edit-done]): focus out of the card,
 *   « pk:refresh-now », back to the block's top (pk_edit_anchor).
 * - Edit-only controls ([data-pk-edit-only], e.g. a red trash) show while
 *   their card is open. A pencil or control outside its card (a top bar)
 *   names it: data-pk-edit-for="<card key>", looked up in the enclosing
 *   edit cards. A folded card (<details>) unfolds first.
 * - data-pk-edit-open-on-load: the card opens on load (scrolled to); a card
 *   rendered open shows its ✓ and controls at once, again after a fragment
 *   refresh (« pk:fragments »).
 * - « pk:edit-open » from inside a card opens it (e.g. a field restoring a
 *   device draft in a hidden edit view). Opening announces
 *   « pk:edit-view-open » on the edit view (pk_lazy_edit) and focuses its
 *   first text field.
 * - A link to « …#<details id> » opens that <details> on the page.
 * - « pk:saved » updates the read views in place:
 *   [data-pk-display="model:id:field"] (pk_display_key on the server) takes
 *   the saved display (and its tap-to-call / email href); a holder marked
 *   data-pk-display-hide-empty shows only while its value is set.
 *
 * Exports setCardEditing(card, editing) and bootEditCards() (what runs on
 * load).
 */
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { pkSetDisplay } from "@bemade_portal_kit/js/pk_contact_href";
import { anchorEdited } from "@bemade_portal_kit/js/pk_edit_anchor";
import { focusFirstField } from "@bemade_portal_kit/js/pk_focus";
import { registerRefreshMarkers } from "@bemade_portal_kit/js/pk_fragments";

// The screen refresh learns the edit cards' markers: an open card holds its
// list (it never moves under the user's hands) and a card's read view keeps
// its hidden state while the card is open.
registerRefreshMarkers({
    editing: ['[data-pk-edit-open]:not([data-pk-edit-open=""])'],
    keepsHidden: ["[data-pk-edit-view]"],
});

const CHECK_PATH = "M20 6L9 17l-5-5";
const pencils = new WeakMap();

function app() {
    return document.querySelector(".o_pk_app[data-pk-app-shell]");
}

function onLoad(fn) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn);
    } else {
        fn();
    }
}

// ---------------------------------------------------------- read views
document.addEventListener("pk:saved", (ev) => {
    const { model, recordId, field, result } = ev.detail || {};
    if (!result) {
        return;
    }
    const show = (el, display) => {
        pkSetDisplay(el, display);
        const holder = el.closest("[data-pk-display-hide-empty]");
        if (holder) {
            holder.hidden = !display;
        }
    };
    const update = (name, display) => {
        const key = CSS.escape(`${model}:${recordId}:${name}`);
        for (const el of document.querySelectorAll(`[data-pk-display="${key}"]`)) {
            show(el, display);
        }
    };
    if (result.display !== undefined) {
        update(field, result.display);
    }
    for (const [name, shown] of Object.entries(result.also || {})) {
        update(name, shown.display);
    }
});

// ---------------------------------------------------------- the ✓
function setToggleDone(toggle, editing) {
    const svg = toggle.querySelector("svg");
    if (editing) {
        if (!pencils.has(toggle)) {
            pencils.set(toggle, {
                icon: svg ? svg.innerHTML : null,
                label: toggle.getAttribute("aria-label"),
                title: toggle.getAttribute("title"),
            });
        }
        if (svg) {
            svg.innerHTML = `<path d="${CHECK_PATH}"/>`;
        }
        // The consumer's label comes translated with the page (a card may
        // open on load, before the script translations are there).
        const root = app();
        const label = (root && root.dataset.pkEditDoneLabel) || _t("Finish editing");
        toggle.setAttribute("aria-label", label);
        toggle.setAttribute("title", label);
        toggle.classList.add("o_pk_edit_toggle_done");
        toggle.dataset.pkEditToggleDone = "1";
        return;
    }
    const saved = pencils.get(toggle);
    if (saved) {
        if (svg && saved.icon !== null) {
            svg.innerHTML = saved.icon;
        }
        for (const [attr, value] of [["aria-label", saved.label], ["title", saved.title]]) {
            if (value === null) {
                toggle.removeAttribute(attr);
            } else {
                toggle.setAttribute(attr, value);
            }
        }
    }
    toggle.classList.remove("o_pk_edit_toggle_done");
    delete toggle.dataset.pkEditToggleDone;
}

// ---------------------------------------------------------- owner card
/** The card a pencil / an edit-only control belongs to. */
function ownerCard(control) {
    const key = control.dataset.pkEditFor;
    const nearest = control.closest("[data-pk-edit-card]");
    if (!key) {
        return nearest;
    }
    let scope = nearest;
    while (scope) {
        const target = scope.querySelector(`[data-pk-edit-card="${CSS.escape(key)}"]`);
        if (target) {
            return target;
        }
        scope = scope.parentElement && scope.parentElement.closest("[data-pk-edit-card]");
    }
    return null;
}

/** A card's own controls (not a nested card's) and the ones naming it. */
function cardControls(card, selector) {
    const own = [...card.querySelectorAll(selector)].filter((el) => ownerCard(el) === card);
    const key = card.dataset.pkEditCard;
    const host = card.parentElement && card.parentElement.closest("[data-pk-edit-card]");
    const outside = key && host
        ? [...host.querySelectorAll(`${selector}[data-pk-edit-for="${CSS.escape(key)}"]`)].filter(
            (el) => !card.contains(el) && ownerCard(el) === card)
        : [];
    return [...own, ...outside];
}

function syncCardControls(card, editing) {
    for (const toggle of cardControls(card, "[data-pk-edit-toggle]")) {
        toggle.setAttribute("aria-expanded", editing ? "true" : "false");
        setToggleDone(toggle, editing);
    }
    for (const control of cardControls(card, "[data-pk-edit-only]")) {
        control.hidden = !editing;
    }
}

/** Open (``editing``) or close an edit card. */
export function setCardEditing(card, editing) {
    const edit = card.querySelector('[data-pk-edit-view="edit"]');
    const read = card.querySelector('[data-pk-edit-view="read"]');
    if (!edit) {
        return;
    }
    edit.hidden = !editing;
    if (read) {
        read.hidden = editing;
    }
    if (editing) {
        card.dataset.pkEditOpen = "1";
    } else {
        delete card.dataset.pkEditOpen;
    }
    syncCardControls(card, editing);
    if (editing) {
        // A lazy edit view mounts its fields now (pk_lazy_edit.js).
        edit.dispatchEvent(new CustomEvent("pk:edit-view-open", { bubbles: true }));
        // A text field only (never a picker), nothing on a phone.
        focusFirstField(edit);
    }
}

// ---------------------------------------------------------- on load
function openCardsOnLoad() {
    for (const card of document.querySelectorAll(".o_pk_app [data-pk-edit-card][data-pk-edit-open-on-load]")) {
        setCardEditing(card, true);
        card.scrollIntoView({ block: "start" });
    }
}

function syncOpenCards() {
    for (const card of document.querySelectorAll(".o_pk_app [data-pk-edit-card][data-pk-edit-open]")) {
        syncCardControls(card, true);
    }
}

function openHashedDetails() {
    const id = (browser.location.hash || "").slice(1);
    const details = id && /^[\w-]+$/.test(id) && document.getElementById(id);
    if (details && details.tagName === "DETAILS" && details.closest(".o_pk_app")) {
        details.open = true;
        details.scrollIntoView({ block: "start" });
    }
}

/** What runs on load (exported for the tests). */
export function bootEditCards() {
    openCardsOnLoad();
    openHashedDetails();
    syncOpenCards();
}

onLoad(bootEditCards);
window.addEventListener("hashchange", openHashedDetails);
// A refreshed read fragment brings its controls back as rendered: re-sync.
document.addEventListener("pk:fragments", syncOpenCards);

document.addEventListener("pk:edit-open", (ev) => {
    const card = ev.target.closest && ev.target.closest(".o_pk_app [data-pk-edit-card]");
    if (card && !card.dataset.pkEditOpen) {
        setCardEditing(card, true);
    }
});

document.addEventListener("click", (ev) => {
    const target = ev.target.closest ? ev.target : null;
    if (!target || !target.closest(".o_pk_app")) {
        return;
    }
    const toggle = target.closest("[data-pk-edit-toggle]");
    const done = !toggle && target.closest("[data-pk-edit-done]");
    const card = toggle ? ownerCard(toggle) : done && done.closest("[data-pk-edit-card]");
    if (!card) {
        return;
    }
    ev.preventDefault();
    if (toggle) {
        // A top-bar pencil of a folded card unfolds it first.
        const fold = card.closest("details:not([open])");
        if (fold && !card.dataset.pkEditOpen) {
            fold.open = true;
        }
        const closing = Boolean(card.dataset.pkEditOpen);
        setCardEditing(card, !closing);
        if (closing) {
            if (card.contains(document.activeElement)) {
                document.activeElement.blur();
            }
            document.dispatchEvent(new CustomEvent("pk:refresh-now"));
            anchorEdited(card);
        }
        return;
    }
    setCardEditing(card, false);
    // The hidden « Done » would keep the focus inside the card (a busy card
    // is never re-ordered or dropped by a list refresh).
    if (done && done.contains(document.activeElement)) {
        document.activeElement.blur();
    }
    document.dispatchEvent(new CustomEvent("pk:refresh-now"));
});
