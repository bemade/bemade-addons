/*
 * Task 1656 — two small shell helpers.
 *
 * scConfirm({title, message, confirm, cancel}) → Promise<boolean>: an app
 * sheet (<dialog class="o_sc_sheet">, built once, reused) with « Cancel » /
 * the confirm button; Escape or a tap outside = cancel.
 *
 * scLeavePage(message): the viewer just lost access to this page (e.g. they
 * removed the only team linking them to a player) — keep ``message`` for a
 * toast on the next page (sessionStorage, shown by sc_app_ui.js) and go back
 * to where they came from: the previous in-app page (document.referrer, same
 * origin, not this page), else /my/players — never this page again, and as a
 * fresh load (location.replace: no back/forward cache copy of the page).
 */
export const PENDING_TOAST_KEY = "sc_pending_toast:v1";

let sheet = null;

function build() {
    const dialog = document.createElement("dialog");
    dialog.className = "o_sc_sheet o_sc_confirm_sheet";
    dialog.setAttribute("aria-labelledby", "sc_confirm_title");
    dialog.dataset.scConfirm = "1";
    dialog.innerHTML = `
        <div class="o_sc_sheet_head"><h2 class="o_sc_sheet_title" id="sc_confirm_title"></h2></div>
        <div class="o_sc_sheet_body">
            <p class="o_sc_confirm_message"></p>
            <div class="o_sc_form_actions">
                <button type="button" class="o_sc_btn o_sc_btn_ghost" data-sc-confirm-cancel="1"></button>
                <button type="button" class="o_sc_btn o_sc_btn_danger" data-sc-confirm-ok="1"></button>
            </div>
        </div>`;
    (document.querySelector(".o_sc_app") || document.body).appendChild(dialog);
    return dialog;
}

export function scConfirm({ title = "", message = "", confirm = "OK", cancel = "Cancel" } = {}) {
    sheet = sheet && sheet.isConnected ? sheet : build();
    const dialog = sheet;
    dialog.querySelector(".o_sc_sheet_title").textContent = title;
    dialog.querySelector(".o_sc_confirm_message").textContent = message;
    const ok = dialog.querySelector("[data-sc-confirm-ok]");
    const no = dialog.querySelector("[data-sc-confirm-cancel]");
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

export function scLeavePage(message) {
    try {
        if (message) {
            window.sessionStorage.setItem(PENDING_TOAST_KEY, String(message));
        }
    } catch {
        // private mode: no toast on the next page
    }
    let target = "/my/players";
    try {
        const ref = document.referrer ? new URL(document.referrer) : null;
        const here = new URL(window.location.href);
        if (ref && ref.origin === here.origin && ref.pathname.startsWith("/my")
                && !(ref.pathname === here.pathname && ref.search === here.search)
                && !(ref.pathname === "/my/player" && ref.searchParams.get("player_id") === here.searchParams.get("player_id"))) {
            target = ref.pathname + ref.search;
        }
    } catch {
        // fall back to the players list
    }
    window.location.replace(target);
}
