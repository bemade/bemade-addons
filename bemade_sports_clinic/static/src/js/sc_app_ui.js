/*
 * Task 1542 (epic #1535) — the clinic's own app shell page behaviours
 * (progressive enhancement; inert outside .o_pk_app).
 *
 * The shell's generic behaviours are the kit's:
 * - task 5371 (P4c1): the toast, the session notification and the undo
 *   offers (pk_toast.js, « pk:toast »);
 * - task 5381 (P4c2): the edit cards (pk_edit_cards.js: pencil ↔ ✓,
 *   « Done », open on load, « pk:edit-open », the read views refreshed on
 *   « pk:saved »), the sheets and lazy bodies (pk_sheets.js), the page tabs
 *   (pk_tabs.js), the clamped texts (pk_clamp.js) and the shell's boot:
 *   drafts purged / cleared, logout, the test database ribbon (pk_shell.js).
 *
 * This file keeps the clinic's hooks on them:
 * - the injury's undo offer (« Injury created · Undo »);
 * - « Add My Timesheet » when I already have a timesheet on this event (a
 *   capture-phase listener: it runs before the kit's sheet opener).
 */
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { setCardEditing } from "@bemade_portal_kit/js/pk_edit_cards";
import { openSheet } from "@bemade_portal_kit/js/pk_sheets";
import { keepClearOfToast, showToast, UNDO_OFFERS } from "@bemade_portal_kit/js/pk_toast";

function app() {
    return document.querySelector(".o_pk_app[data-pk-app-shell]");
}

// A just-created injury (inline « Add Injury », owner decision 2026-10-11):
// « Injury created · Undo » for the undo window (the server enforces it
// too; task 5371: the kit's undo offer, form[data-pk-undo-offer="injury"]),
// and the address loses ?created= for ?injury= so a reload opens the injury
// without offering the undo again. Task 1679: the card, scrolled to at
// once, is lifted above the toast when it fits.
registry.category(UNDO_OFFERS).add("injury", {
    rewriteUrl(url) {
        if (url.searchParams.has("created")) {
            url.searchParams.set("injury", url.searchParams.get("created"));
        }
    },
    after({ form }) {
        const card = form.closest("[data-sc-created-injury]");
        if (card) {
            card.scrollIntoView({ block: "start", behavior: "instant" });
            keepClearOfToast(card, { fitOnly: true });
        }
    },
});

// Task 1665: « Add My Timesheet » when I already have an editable timesheet
// on this event — open THAT card in edit (scrolled to), and a toast offers
// « Add another timesheet » (the add sheet, split shifts). The sheet's own
// « Edit my timesheet » does the same from inside it.
function editExistingTimesheet(id, behavior) {
    const card = document.querySelector(`.o_pk_app [data-sc-timesheet-id="${id}"][data-pk-edit-card]`);
    if (!card) {
        return false;
    }
    setCardEditing(card, true);
    card.scrollIntoView({ block: "center", behavior: behavior || "auto" });
    return card;
}

// Capture phase: runs before the kit's sheet opener (pk_sheets.js), which
// it pre-empts when the card is on the page.
document.addEventListener("click", (ev) => {
    const root = app();
    if (!root || !root.contains(ev.target)) {
        return;
    }
    const add = ev.target.closest('[data-sc-action="timesheet.add"][data-pk-sheet-open]');
    const edit = !add && ev.target.closest("[data-sc-ts-edit]");
    if (!add && !edit) {
        return;
    }
    const holder = root.querySelector("[data-sc-ts-existing-id]");
    const id = edit ? edit.dataset.scTsEdit : holder && holder.dataset.scTsExistingId;
    if (!id) {
        return;
    }
    const dialog = edit && edit.closest("dialog");
    // Task 1679: an instant scroll when the toast follows (it then lifts
    // the card above itself).
    const card = editExistingTimesheet(id, add ? "instant" : undefined);
    if (!card) {
        return; // no card on this page: let the sheet open as usual
    }
    ev.preventDefault();
    ev.stopImmediatePropagation();
    if (dialog) {
        dialog.close();
    }
    if (add) {
        showToast(_t("You already have a timesheet for this event."), _t("Add another timesheet"),
            () => openSheet(add.dataset.pkSheetOpen || "sc_ts_add_sheet"));
        // Task 1679: its « Delete » / « Done » never sit under the toast.
        keepClearOfToast(card);
    }
}, true);
