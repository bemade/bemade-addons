/*
 * Task 1656 — two small shell helpers. Task 5197 (P2): moved from
 * bemade_sports_clinic (sc_confirm.js) to the portal kit; the « home » is no
 * longer hard-coded (see pkLeaveTarget).
 *
 * pkConfirm({title, message, confirm, cancel}) → Promise<boolean>: an app
 * sheet (<dialog class="o_pk_sheet">, built once, reused) with « Cancel » /
 * the confirm button; Escape or a tap outside = cancel.
 *
 * pkLeavePage(message): the viewer just lost access to this page (e.g. they
 * removed the only team linking them to a player) — keep ``message`` for a
 * toast on the next page (sessionStorage, shown by sc_app_ui.js) and go back
 * to where they came from: the previous in-app page (document.referrer, same
 * origin, not this page), else the app's home — never this page again, and
 * as a fresh load (location.replace: no back/forward cache copy of the page).
 *
 * The home and « this page » come from the shell root:
 *   data-pk-home="/my/things"               the home (default: /my);
 *   data-pk-home-same-params="thing_id,…"   the query params that name the
 *       RECORD of a page: a referrer with the same value for each of them
 *       (one at least set) shows the same record — the one access was lost
 *       to — on whatever path (its main page, a sub-page), so it is skipped.
 *       Without it (or when neither URL has one of them), « this page » is
 *       the same path and query.
 */
export const PENDING_TOAST_KEY = "pk_pending_toast:v1";

let sheet = null;

function build() {
    const dialog = document.createElement("dialog");
    dialog.className = "o_pk_sheet o_pk_confirm_sheet";
    dialog.setAttribute("aria-labelledby", "sc_confirm_title");
    dialog.dataset.pkConfirm = "1";
    dialog.innerHTML = `
        <div class="o_pk_sheet_head"><h2 class="o_pk_sheet_title" id="sc_confirm_title"></h2></div>
        <div class="o_pk_sheet_body">
            <p class="o_pk_confirm_message"></p>
            <div class="o_pk_form_actions">
                <button type="button" class="o_pk_btn o_pk_btn_ghost" data-pk-confirm-cancel="1"></button>
                <button type="button" class="o_pk_btn o_pk_btn_danger" data-pk-confirm-ok="1"></button>
            </div>
        </div>`;
    (document.querySelector(".o_pk_app") || document.body).appendChild(dialog);
    return dialog;
}

export function pkConfirm({ title = "", message = "", confirm = "OK", cancel = "Cancel" } = {}) {
    sheet = sheet && sheet.isConnected ? sheet : build();
    const dialog = sheet;
    dialog.querySelector(".o_pk_sheet_title").textContent = title;
    dialog.querySelector(".o_pk_confirm_message").textContent = message;
    const ok = dialog.querySelector("[data-pk-confirm-ok]");
    const no = dialog.querySelector("[data-pk-confirm-cancel]");
    ok.textContent = confirm;
    no.textContent = cancel;
    return new Promise((resolve) => {
        let done = false;
        const finish = (value) => {
            if (done) {
                return;
            }
            done = true;
            ok.removeEventListener("click", onOk);
            no.removeEventListener("click", onNo);
            dialog.removeEventListener("close", onClose);
            if (dialog.open) {
                dialog.close();
            }
            resolve(value);
        };
        const onOk = () => finish(true);
        const onNo = () => finish(false);
        const onClose = () => finish(false);
        ok.addEventListener("click", onOk);
        no.addEventListener("click", onNo);
        dialog.addEventListener("close", onClose);
        if (typeof dialog.showModal === "function") {
            dialog.showModal();
        }
        no.focus();
    });
}

/** The home settings of a shell root (``[data-pk-home]``). */
export function pkHomeOf(root) {
    const home = (root && root.dataset.pkHome) || "/my";
    const raw = root && root.dataset.pkHomeSameParams;
    const sameParams = raw ? raw.split(",").map((name) => name.trim()).filter(Boolean) : [];
    return { home, sameParams: sameParams.length ? sameParams : null };
}

function sameRecord(ref, here, sameParams) {
    if (ref.pathname === here.pathname && ref.search === here.search) {
        return true;
    }
    const named = (sameParams || []).filter(
        (name) => here.searchParams.has(name) || ref.searchParams.has(name)
    );
    return (
        named.length > 0 &&
        named.every((name) => ref.searchParams.get(name) === here.searchParams.get(name))
    );
}

/**
 * Where pkLeavePage goes from ``hereUrl``: the in-app ``referrer`` (same
 * origin, under /my, not the same record), else ``home``.
 */
export function pkLeaveTarget(hereUrl, referrer, { home = "/my", sameParams = null } = {}) {
    try {
        const ref = referrer ? new URL(referrer) : null;
        const here = new URL(hereUrl);
        if (
            ref &&
            ref.origin === here.origin &&
            ref.pathname.startsWith("/my") &&
            !sameRecord(ref, here, sameParams)
        ) {
            return ref.pathname + ref.search;
        }
    } catch {
        // fall back to the home
    }
    return home;
}

export function pkLeavePage(message) {
    try {
        if (message) {
            window.sessionStorage.setItem(PENDING_TOAST_KEY, String(message));
        }
    } catch {
        // private mode: no toast on the next page
    }
    const settings = pkHomeOf(document.querySelector("[data-pk-home]"));
    window.location.replace(pkLeaveTarget(window.location.href, document.referrer, settings));
}
