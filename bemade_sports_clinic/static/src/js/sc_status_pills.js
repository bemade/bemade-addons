/*
 * Task 1627 — status pill dropdowns (the shared « sc_status_pill_select »
 * component, views/sc_components.xml). Inert outside .o_sc_app.
 *
 * A pill is [data-sc-pill-select] holding its target (data-sc-model,
 * -record-id, -field, -write-date, -old-value, -undo-message), a toggle
 * button[data-sc-menu-toggle] and a [data-sc-menu-popup] of
 * button[role="menuitemradio"] items (data-sc-pill-post = the value a pick
 * saves; aria-disabled = greyed, with its hint, posts nothing).
 *
 * - The menu is sc_user_menu.js's (keyboard: arrows / Home / End / Escape /
 *   Tab / Space; outside tap; one open at a time). Clicks on the toggle and
 *   the items are handled HERE in the capture phase (preventDefault +
 *   stopPropagation): inside a <summary> a pick never toggles the card.
 * - A pick POSTs /my/app/save/<model>/<id> {field, value, write_date,
 *   old_value} (the values rendered in the read fragment), then closes the
 *   menu, BLURS (sc_fragments never swaps the node holding the focus),
 *   announces « sc:saved » (the read fragments refresh in place), and shows
 *   the « Annuler » toast (re-posts the previous value).
 * - Until the fresh fragment lands, the record's pills are busy (a second
 *   pick waits for the fresh values instead of posting stale ones); the
 *   pills' write_date / old_value are also updated at once.
 * - A 409 (changed elsewhere) or any refusal: a toast, and the record's
 *   fragments are refreshed.
 * - Task 1631: an item with data-sc-pill-action posts nothing here: the
 *   menu closes, the pill blurs and an « sc:pill-action » event
 *   ({action, value, from, model, recordId, pill}) hands the pick to the
 *   module owning that action (the injury stage's verify / resolve flows).
 *   An empty data-sc-pill-post is a value (a blank choice); only a missing
 *   one means « nothing to post ».
 */
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
import { requestRefresh } from "@bemade_sports_clinic/js/sc_fragments";
import { close, closeAll, open } from "@bemade_sports_clinic/js/sc_user_menu";

const PILL = "[data-sc-pill-select]";
const BUSY_MS = 8000;

function inShell(node) {
    return Boolean(node && node.closest(".o_sc_app"));
}

function toast(detail) {
    document.dispatchEvent(new CustomEvent("sc:toast", { detail }));
}

function toggleOf(pill) {
    return pill.querySelector("[data-sc-menu-toggle]");
}

/** Every pill of the same record field on the page (e.g. Match + Practice). */
function siblings(pill) {
    const { scModel, scRecordId, scField } = pill.dataset;
    return [...document.querySelectorAll(PILL)].filter(
        (el) =>
            el.dataset.scModel === scModel &&
            el.dataset.scRecordId === scRecordId &&
            el.dataset.scField === scField
    );
}

function setBusy(pills, busy) {
    for (const el of pills) {
        if (busy) {
            el.setAttribute("aria-busy", "true");
        } else {
            el.removeAttribute("aria-busy");
        }
    }
}

function refreshRecord(pill) {
    requestRefresh([`${pill.dataset.scModel}:${pill.dataset.scRecordId}:*`], { immediate: true });
}

/**
 * Save ``value`` on the pill's target. Reads write_date / old_value from the
 * DOM at call time (the undo runs after the fragment was swapped).
 */
async function save(pill, value) {
    const { scModel: model, scRecordId: recordId, scField: field } = pill.dataset;
    const pills = siblings(pill);
    setBusy(pills, true);
    const timer = setTimeout(() => setBusy(siblings(pill), false), BUSY_MS);
    try {
        const result = await scFetch(`/my/app/save/${encodeURIComponent(model)}/${recordId}`, {
            method: "POST",
            data: {
                field,
                value,
                write_date: pill.dataset.scWriteDate,
                old_value: pill.dataset.scOldValue,
            },
            toast: false,
        });
        // The fresh fragment will carry these too; meanwhile, never stale.
        for (const el of pills) {
            el.dataset.scWriteDate = result.write_date;
            el.dataset.scOldValue = result.value !== undefined ? String(result.value) : value;
        }
        document.dispatchEvent(
            new CustomEvent("sc:saved", {
                detail: { model, recordId: Number(recordId), field, result },
            })
        );
        refreshRecord(pill);
        return result;
    } catch (err) {
        clearTimeout(timer);
        setBusy(siblings(pill), false);
        const conflict = err && err.status === 409;
        toast({
            message: conflict
                ? _t("Changed elsewhere")
                : (err && err.payload && err.payload.message) || _t("Error — not saved"),
        });
        refreshRecord(pill);
        return null;
    }
}

async function pick(pill, item) {
    const toggle = toggleOf(pill);
    if (toggle) {
        close(toggle);
        toggle.blur();
    }
    item.blur();
    // Task 1721 (review round 1): WebKit leaves a tap's focus on the card's
    // <summary> — a focused card never moves in its list (sc_fragments.js),
    // e.g. a resolved injury set back to « Actif » joining the active ones.
    const held = document.activeElement;
    if (held && held !== document.body && held.closest && held.closest("[data-sc-fragment-item]")) {
        held.blur();
    }
    const value = item.dataset.scPillPost;
    const previous = pill.dataset.scOldValue;
    const { scModel, scRecordId, scField } = pill.dataset;
    const result = await save(pill, value);
    if (!result || previous === undefined) {
        return;
    }
    toast({
        message: pill.dataset.scUndoMessage || _t("Change saved"),
        actionLabel: _t("Undo"),
        action: () => {
            // The pill as it is NOW (the fragment may have been swapped).
            const current = [...document.querySelectorAll(PILL)].find(
                (el) =>
                    el.dataset.scModel === scModel &&
                    el.dataset.scRecordId === scRecordId &&
                    el.dataset.scField === scField
            );
            if (current) {
                save(current, previous);
            }
        },
    });
}

/** Task 1631: a pick another module acts on (no save here). */
function handOff(pill, item) {
    const toggle = toggleOf(pill);
    if (toggle) {
        close(toggle);
        toggle.blur();
    }
    item.blur();
    document.dispatchEvent(
        new CustomEvent("sc:pill-action", {
            detail: {
                action: item.dataset.scPillAction,
                value: item.dataset.scPillValue,
                from: item.dataset.scPillFrom || "",
                model: pill.dataset.scModel,
                recordId: Number(pill.dataset.scRecordId),
                pill,
            },
        })
    );
}

// A keyboard pick: once the fresh pill is in, the focus goes back to it.
let refocus = null;
document.addEventListener("sc:fragments", () => {
    if (!refocus) {
        return;
    }
    const { model, recordId, field, key } = refocus;
    const fresh = [...document.querySelectorAll(PILL)].find(
        (el) =>
            el.dataset.scModel === model &&
            el.dataset.scRecordId === recordId &&
            el.dataset.scField === field &&
            el.dataset.scPillKey === key
    );
    const toggle = fresh && toggleOf(fresh);
    if (toggle && fresh.getAttribute("aria-busy") !== "true") {
        refocus = null;
        toggle.focus();
    }
});

document.addEventListener(
    "click",
    (ev) => {
        const target = ev.target;
        const pill = target && target.closest && target.closest(PILL);
        if (!pill || !inShell(pill)) {
            return;
        }
        const toggle = target.closest("[data-sc-menu-toggle]");
        const item = target.closest('[role="menuitemradio"]');
        if (!toggle && !item) {
            return; // the popup's padding: nothing to do, stay open
        }
        // Inside <summary>: act, never toggle the card.
        ev.preventDefault();
        ev.stopPropagation();
        if (toggle) {
            if (toggle.getAttribute("aria-expanded") === "true") {
                close(toggle);
            } else if (pill.getAttribute("aria-busy") === "true") {
                closeAll();
            } else {
                open(toggle);
            }
            return;
        }
        if (item.getAttribute("aria-disabled") === "true") {
            return; // greyed: its hint says why; the menu stays open
        }
        if (item.getAttribute("aria-checked") === "true") {
            close(toggleOf(pill), { focus: true });
            return;
        }
        if (item.dataset.scPillAction) {
            handOff(pill, item);
            return;
        }
        if (item.dataset.scPillPost === undefined) {
            close(toggleOf(pill), { focus: true });
            return;
        }
        // A click without a pointer (Enter / Space on the item): keep the
        // keyboard user's place once the pill is re-rendered.
        refocus =
            ev.detail === 0
                ? {
                      model: pill.dataset.scModel,
                      recordId: pill.dataset.scRecordId,
                      field: pill.dataset.scField,
                      key: pill.dataset.scPillKey,
                  }
                : null;
        pick(pill, item);
    },
    true
);
