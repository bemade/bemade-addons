/*
 * Task 1604 — quick « Vérifier » / « Résoudre » of an injury (inert outside
 * .o_sc_app). Therapists only: the buttons and the sheet are rendered for
 * them alone, and the routes refuse anyone else.
 *
 * - button[data-sc-injury-quick="verify"] (an unverified injury's card row
 *   — task 1616: the injury page is the open card): ONE tap posts /my/injury/<id>/verify;
 * - button[data-sc-injury-quick="resolve"] (an active one): opens the
 *   layout's #sc_injury_resolve_sheet (« Résoudre cette blessure ? », the
 *   resolution date, default today); its confirm posts
 *   /my/injury/<id>/resolve with that date.
 *
 * The buttons sit in the card's <summary>: a click acts and never toggles
 * the card. The answer is shaped like a save of ``stage`` and announced as
 * an « sc:saved »: the status island, the read views and the read fragments
 * (summary, card order, the player's lists — task 1611) follow in place, and
 * a ``propose`` opens the follow-up sheet (task 1603: the last active injury
 * resolved -> clear Retour prévu + actual return).
 *
 * Task 1631: the card header's status pill (#1627's component) hands two of
 * its picks over here (« sc:pill-action »): « Actif » from « Non vérifié »
 * = the verify above, « Résolu » = the resolve sheet above (from
 * « Non vérifié » too: the sheet then posts ``from_unverified=1``).
 *
 * Task 1641: a read fragment holding the focus is never swapped
 * (sc_fragments.js), and WebKit (Safari, Chrome on iPhone) never focuses a
 * tapped button — the focus lands on the card's <summary>, so blurring the
 * button left the summary focused; the native <dialog> then gave that focus
 * back on close and the card never showed « Résolu ». The focus is released
 * from any read fragment before the sheet opens and again after it closes.
 */
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
import { requestRefresh } from "@bemade_sports_clinic/js/sc_fragments";

const MODEL = "sports.patient.injury";
const SHEET_ID = "sc_injury_resolve_sheet";

function inShell(node) {
    return Boolean(node && node.closest(".o_sc_app"));
}

function toast(message) {
    if (message) {
        document.dispatchEvent(new CustomEvent("sc:toast", { detail: { message } }));
    }
}

/** Announce the answer like an autosave of the injury's status. */
function announce(injuryId, result) {
    document.dispatchEvent(
        new CustomEvent("sc:saved", {
            detail: { model: MODEL, recordId: Number(injuryId), field: "stage", result },
        })
    );
    toast(result.message);
}

/** A refused action: the row may be stale (someone else acted) — refresh it. */
function refreshInjury(injuryId) {
    requestRefresh([`${MODEL}:${injuryId}:*`], { immediate: true });
}

/**
 * Task 1641: let go of a focus held inside a read fragment (the card's
 * summary or anything in it) so the refresh that follows can swap it.
 */
function releaseFragmentFocus() {
    const active = document.activeElement;
    if (active && active !== document.body && active.closest && active.closest("[data-sc-fragment]")) {
        active.blur();
    }
}

async function post(injuryId, action, data = {}) {
    return scFetch(`/my/injury/${injuryId}/${action}`, { method: "POST", data, toast: false });
}

async function verify(button, injuryId = button.dataset.scInjuryId) {
    button.disabled = true;
    try {
        const result = await post(injuryId, "verify");
        // The summary fragment is not swapped while it holds the focus
        // (task 1641: wherever the tap left it — the button or the summary).
        button.blur();
        releaseFragmentFocus();
        announce(injuryId, result);
    } catch (err) {
        button.disabled = false;
        toast((err && err.payload && err.payload.message) || _t("The injury could not be verified."));
        refreshInjury(injuryId);
    }
}

function resolveSheet() {
    return document.getElementById(SHEET_ID);
}

/** The injury's name, as its card row / page title shows it. */
function injuryName(button) {
    const row = button.closest("summary");
    const title = row
        ? row.querySelector(".o_sc_row_title")
        : document.querySelector(".o_sc_appbar_title_text");
    return title ? title.textContent.trim() : "";
}

function openResolve(button, injuryId = button.dataset.scInjuryId, fromStage = "") {
    const dialog = resolveSheet();
    if (!dialog || typeof dialog.showModal !== "function") {
        return;
    }
    const form = dialog.querySelector("form[data-sc-injury-resolve-form]");
    const input = form.querySelector('input[name="resolution_date"]');
    form.dataset.scInjuryId = injuryId;
    form.dataset.scFromUnverified = fromStage === "unverified" ? "1" : "";
    input.value = input.max || input.defaultValue;
    form.querySelector("[data-sc-injury-resolve-name]").textContent = injuryName(button);
    form.querySelector("[data-sc-injury-resolve-error]").hidden = true;
    form.querySelector("[data-sc-injury-resolve-confirm]").disabled = false;
    button.blur();
    // Task 1641: the dialog gives back on close the focus it found on open.
    releaseFragmentFocus();
    if (!dialog.open) {
        dialog.showModal();
    }
}

async function confirmResolve(form) {
    const injuryId = form.dataset.scInjuryId;
    const input = form.querySelector('input[name="resolution_date"]');
    const error = form.querySelector("[data-sc-injury-resolve-error]");
    const confirm = form.querySelector("[data-sc-injury-resolve-confirm]");
    if (!injuryId) {
        return;
    }
    if (!form.reportValidity()) {
        return;
    }
    confirm.disabled = true;
    error.hidden = true;
    try {
        const data = { resolution_date: input.value };
        if (form.dataset.scFromUnverified === "1") {
            data.from_unverified = "1";
        }
        const result = await post(injuryId, "resolve", data);
        form.closest("dialog").close();
        // Task 1641: the focus the dialog restored must not pin the card.
        releaseFragmentFocus();
        announce(injuryId, result);
    } catch (err) {
        const message = err && err.payload && err.payload.message;
        if (message) {
            error.textContent = message;
        }
        error.hidden = false;
        confirm.disabled = false;
        refreshInjury(injuryId);
    }
}

document.addEventListener(
    "click",
    (ev) => {
        const button = ev.target.closest && ev.target.closest("button[data-sc-injury-quick]");
        if (!button || !inShell(button)) {
            return;
        }
        // Inside <summary>: act, never toggle the card.
        ev.preventDefault();
        ev.stopPropagation();
        if (button.disabled) {
            return;
        }
        if (button.dataset.scInjuryQuick === "verify") {
            verify(button);
        } else if (button.dataset.scInjuryQuick === "resolve") {
            openResolve(button);
        }
    },
    true
);

document.addEventListener("submit", (ev) => {
    const form = ev.target;
    if (!(form instanceof HTMLFormElement) || !form.matches("form[data-sc-injury-resolve-form]") || !inShell(form)) {
        return;
    }
    ev.preventDefault();
    confirmResolve(form);
});

// Task 1631: the status pill's verify / resolve picks.
document.addEventListener("sc:pill-action", (ev) => {
    const detail = ev.detail || {};
    if (detail.model !== MODEL || !detail.pill || !inShell(detail.pill)) {
        return;
    }
    const toggle = detail.pill.querySelector("[data-sc-menu-toggle]") || detail.pill;
    if (detail.action === "injury.verify") {
        verify(toggle, detail.recordId);
    } else if (detail.action === "injury.resolve") {
        openResolve(toggle, detail.recordId, detail.from);
    }
});
