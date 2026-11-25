/*
 * The shell's toast (moved to the kit by task 5371, P4c1). Inert outside
 * .o_pk_app[data-pk-app-shell]; the host is bemade_portal_kit.pk_toast_host
 * (one .o_pk_toast per page).
 *
 * - showToast(message, actionLabel, action, duration, {title, tone}): one
 *   toast at a time, with at most ONE action button
 *   (button.o_pk_toast_action[data-pk-toast-action]); the tone is written
 *   to data-pk-toast-tone. Gone after ``duration`` (default 4 s, 8 s with
 *   an action). While a modal <dialog> is open, the toast goes into it (the
 *   page behind a modal is inert) and back to its place when it closes.
 * - « pk:toast » on the document ({message, actionLabel, action, duration,
 *   title, tone}) shows a toast: the other scripts ask for theirs this way.
 * - keepClearOfToast(el, {fitOnly}): a card the toast is about keeps its
 *   bottom above the toast (the page scrolls by the overlap; room is made
 *   under the page while the toast shows: body[data-pk-toast-room]).
 * - On load (bootToasts):
 *   - the session notification of a POST round-trip, rendered on the host
 *     (data-pk-notify, -notify-title, -notify-tone, -notify-id): shown
 *     once — never on a page shown again by back / forward, never twice for
 *     the same id in this tab (sessionStorage « pk_notify_shown:v1 »; the
 *     list kept under the consumer's former key is moved once). With a
 *     hidden form[data-pk-undo] on the page (an archive's « Undo »), the
 *     toast's action posts that form;
 *   - the pending toast left by the previous page (PENDING_TOAST_KEY);
 *   - the undo offers: a hidden form[data-pk-undo-offer="<kind>"] carrying
 *     data-pk-toast-message, data-pk-toast-action, optional data-pk-undo-ms
 *     (default UNDO_MS) and data-pk-undo-param (a URL parameter dropped with
 *     history.replaceState, so a reload does not offer it again) is offered
 *     once: its toast's action submits the form. Optional hooks per kind in
 *     the registry « pk_undo_offers »: {rewriteUrl(url, form) (before the
 *     parameter is dropped), after({form, root}) (once the toast shows)}.
 * - pk_fetch errors (« pk:fetch-error ») and offline / back online are
 *   toasts.
 */
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { PENDING_TOAST_KEY } from "@bemade_portal_kit/js/pk_confirm";
import { markDirty } from "@bemade_portal_kit/js/pk_fragments";

export const NOTIFY_SHOWN_KEY = "pk_notify_shown:v1";
// The first consumer's key for the same list (read once, then moved).
const OLD_NOTIFY_SHOWN_KEY = "sc_notify_shown:v1";
/** How long an undo stays offered (ms) unless the form says otherwise. */
export const UNDO_MS = 8000;
/** The registry category of the undo offers' hooks, keyed by kind. */
export const UNDO_OFFERS = "pk_undo_offers";

const NOTIFY_KEEP = 20;

function app() {
    return document.querySelector(".o_pk_app[data-pk-app-shell]");
}

function hostOf(root) {
    return root && root.querySelector(".o_pk_toast");
}

// ---------------------------------------------------------------- toast
let toastTimer = null;
let toastHome = null;

function placeToast(root, toast) {
    if (!toastHome && !toast.closest("dialog")) {
        toastHome = toast.parentElement;
    }
    if (toastHome && !toastHome.isConnected) {
        toastHome = toast.closest("dialog") ? null : toast.parentElement;
    }
    const modal = [...root.querySelectorAll("dialog[open]")].pop();
    if (modal && toast.parentElement !== modal) {
        modal.appendChild(toast);
    } else if (!modal && toastHome && toast.parentElement !== toastHome) {
        toastHome.appendChild(toast);
    }
}

document.addEventListener(
    "close",
    (ev) => {
        const toast = ev.target instanceof HTMLDialogElement && ev.target.querySelector(":scope > .o_pk_toast");
        if (toast && toastHome) {
            toastHome.appendChild(toast);
        }
    },
    true
);

export function showToast(message, actionLabel, action, duration, options) {
    const root = app();
    const toast = hostOf(root);
    if (!toast) {
        return;
    }
    placeToast(root, toast);
    const { title, tone } = options || {};
    // The title sits above the text (one column), the action button beside
    // that column — under it, right-aligned, when it does not fit.
    const body = document.createElement("span");
    body.className = "o_pk_toast_body";
    if (title) {
        const strong = document.createElement("strong");
        strong.className = "o_pk_toast_title";
        strong.textContent = title;
        body.appendChild(strong);
    }
    const text = document.createElement("span");
    text.className = "o_pk_toast_text";
    text.textContent = message;
    body.appendChild(text);
    const parts = [body];
    if (tone) {
        toast.dataset.pkToastTone = tone;
    } else {
        delete toast.dataset.pkToastTone;
    }
    if (actionLabel && action) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "o_pk_toast_action";
        button.dataset.pkToastAction = "1";
        button.textContent = actionLabel;
        button.addEventListener("click", () => {
            toast.hidden = true;
            action();
        });
        parts.push(button);
    }
    toast.replaceChildren(...parts);
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.hidden = true;
    }, duration || (actionLabel ? UNDO_MS : 4000));
}

/**
 * A card the toast is about keeps its bottom (its buttons) above the toast
 * (fixed over the page): the page scrolls up by the overlap, with room made
 * under the page when it is already at its end (removed with the toast).
 * Call it once the card's own scroll is done (an instant one). ``fitOnly``:
 * only when the whole card fits above the toast.
 */
export function keepClearOfToast(el, { fitOnly = false } = {}) {
    const toast = hostOf(app());
    if (!el || !toast || toast.hidden) {
        return;
    }
    const gap = 8;
    const toastTop = toast.getBoundingClientRect().top;
    const rect = el.getBoundingClientRect();
    const overlap = rect.bottom - (toastTop - gap);
    if (overlap <= 0 || (fitOnly && rect.height > toastTop - gap)) {
        return;
    }
    const scroller = document.scrollingElement || document.documentElement;
    const room = window.scrollY + overlap - (scroller.scrollHeight - window.innerHeight);
    if (room > 0 && !document.body.dataset.pkToastRoom) {
        document.body.dataset.pkToastRoom = "1";
        document.body.style.paddingBottom = `${Math.ceil(room)}px`;
        const observer = new MutationObserver(() => {
            if (toast.hidden) {
                observer.disconnect();
                delete document.body.dataset.pkToastRoom;
                document.body.style.paddingBottom = "";
            }
        });
        observer.observe(toast, { attributes: true, attributeFilter: ["hidden"] });
    }
    window.scrollBy({ top: overlap, behavior: "instant" });
}

document.addEventListener("pk:toast", (ev) => {
    const detail = ev.detail || {};
    showToast(detail.message || "", detail.actionLabel, detail.action, detail.duration, {
        title: detail.title,
        tone: detail.tone,
    });
});

// --------------------------------------------------- session notification
function navigationType() {
    try {
        const entry = performance.getEntriesByType("navigation")[0];
        return (entry && entry.type) || "navigate";
    } catch {
        return "navigate";
    }
}

/** The ids shown in this tab; the former key's list is moved once. */
function readShown(store) {
    const shown = JSON.parse(store.getItem(NOTIFY_SHOWN_KEY) || "[]");
    const old = store.getItem(OLD_NOTIFY_SHOWN_KEY);
    if (old !== null) {
        store.removeItem(OLD_NOTIFY_SHOWN_KEY);
        let ids = [];
        try {
            ids = JSON.parse(old);
        } catch {
            ids = [];
        }
        for (const id of Array.isArray(ids) ? ids : []) {
            if (!shown.includes(id)) {
                shown.push(id);
            }
        }
        store.setItem(NOTIFY_SHOWN_KEY, JSON.stringify(shown.slice(-NOTIFY_KEEP)));
    }
    return shown;
}

/** True when ``id`` was shown already; else remembers it (last 20). */
function notificationSeen(id) {
    if (!id) {
        return false;
    }
    try {
        const store = window.sessionStorage;
        const shown = readShown(store);
        if (shown.includes(id)) {
            return true;
        }
        shown.push(id);
        store.setItem(NOTIFY_SHOWN_KEY, JSON.stringify(shown.slice(-NOTIFY_KEEP)));
    } catch {
        // private mode / storage off: the navigation-type check still applies
    }
    return false;
}

/** An undo's action: the session changes (pages shown again by « back »
 * reload: form.submit() fires no « submit » event), then the form posts. */
function submitUndo(form) {
    return () => {
        markDirty();
        form.submit();
    };
}

function showSessionNotification() {
    const root = app();
    const toast = root && root.querySelector(".o_pk_toast[data-pk-notify]");
    if (!toast) {
        return;
    }
    const message = toast.dataset.pkNotify;
    const tone = toast.dataset.pkNotifyTone || "success";
    const title = toast.dataset.pkNotifyTitle || "";
    const id = toast.dataset.pkNotifyId || "";
    delete toast.dataset.pkNotify;
    delete toast.dataset.pkNotifyTitle;
    delete toast.dataset.pkNotifyTone;
    delete toast.dataset.pkNotifyId;
    if (navigationType() === "back_forward" || notificationSeen(id)) {
        return;
    }
    // An archive just done: its « Undo » posts the restore form.
    const undo = root.querySelector("form[data-pk-undo]");
    if (undo) {
        showToast(message, undo.dataset.pkToastAction, submitUndo(undo), UNDO_MS, { title, tone });
        return;
    }
    showToast(message, null, null, tone === "error" ? 10000 : 6000, { title, tone });
}

// ------------------------------------------------------------ pending toast
function showPendingToast() {
    let message = null;
    try {
        message = window.sessionStorage.getItem(PENDING_TOAST_KEY);
        window.sessionStorage.removeItem(PENDING_TOAST_KEY);
    } catch {
        return;
    }
    if (message && app()) {
        showToast(message);
    }
}

// --------------------------------------------------------------- undo offers
/** Offer the page's undo forms (each once). */
export function offerUndos() {
    const root = app();
    if (!root) {
        return;
    }
    const hooks = registry.category(UNDO_OFFERS);
    for (const form of root.querySelectorAll("form[data-pk-undo-offer]:not([data-pk-undo-offered])")) {
        form.dataset.pkUndoOffered = "1";
        const kind = form.dataset.pkUndoOffer;
        const hook = hooks.get(kind, null) || {};
        const ms = Number(form.dataset.pkUndoMs) || UNDO_MS;
        showToast(form.dataset.pkToastMessage || "", form.dataset.pkToastAction, submitUndo(form), ms);
        const param = form.dataset.pkUndoParam;
        try {
            const url = new URL(browser.location.href);
            const before = url.toString();
            if (hook.rewriteUrl) {
                hook.rewriteUrl(url, form);
            }
            if (param) {
                url.searchParams.delete(param);
            }
            if (url.toString() !== before) {
                browser.history.replaceState(browser.history.state, "", url.toString());
            }
        } catch {
            // the address stays: the server re-checks the undo window
        }
        if (hook.after) {
            hook.after({ form, root });
        }
    }
}

/** Everything the toast shows on load (exported for the tests). */
export function bootToasts() {
    showSessionNotification();
    showPendingToast();
    offerUndos();
}

// The consumers' scripts (and their undo hooks) are evaluated in the same
// bundle after this module: on an already loaded page, wait for them.
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootToasts);
} else {
    setTimeout(bootToasts);
}

// --------------------------------------------------- fetch errors, offline
document.addEventListener("pk:fetch-error", (ev) => {
    const error = ev.detail || {};
    if (error.status === 0) {
        showToast(_t("No connection. Try again when you are back online."));
    } else {
        showToast(_t("Something went wrong. Please try again."));
    }
});
window.addEventListener("offline", () => app() && showToast(_t("You are offline.")));
window.addEventListener("online", () => app() && showToast(_t("Back online.")));
