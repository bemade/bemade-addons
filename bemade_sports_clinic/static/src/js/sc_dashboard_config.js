/*
 * Task 1624 — « Configurer le tableau de bord » (/my/app/dashboard/configure).
 * Inert outside .o_sc_app.
 *
 * Each instance row is ONE form (form[data-sc-dash-instance]) posting to
 * /my/app/dashboard/configure/save. Saved as you go: any change in the form
 * (the on / off switch, a « Portée » picker — the form-mode tag fields write
 * their hidden input and fire « change » —, a filter) is posted at once with
 * fetch; the title after a pause in typing. The server answers JSON
 * {ok} / {ok: false, error}: a refusal shows INSIDE the form
 * ([data-sc-guard-error], #1658), nothing else moves; a success shows
 * « Enregistré » in the row's status line. The « Save » button is the no-JS
 * fallback (hidden here).
 *
 * « Rétablir par défaut » asks first (scConfirm; texts from the form's
 * data-sc-confirm-* attributes, translated server-side).
 */
import { _t } from "@web/core/l10n/translation";
import { scConfirm } from "@bemade_sports_clinic/js/sc_confirm";

const TITLE_DELAY = 700;
const timers = new WeakMap();

function inApp(el) {
    return Boolean(el && el.closest && el.closest(".o_sc_app"));
}

function instanceForm(target) {
    const form = target && target.closest && target.closest("form[data-sc-dash-instance]");
    return form && inApp(form) ? form : null;
}

function fields(form) {
    const data = {};
    const kinds = [];
    for (const [name, value] of new FormData(form).entries()) {
        if (name === "kinds") {
            kinds.push(value);
        } else {
            data[name] = value;
        }
    }
    return { data, kinds };
}

function setStatus(form, text) {
    const status = form.querySelector("[data-sc-dash-status]");
    if (status) {
        status.textContent = text;
    }
}

function setError(form, message) {
    const slot = form.querySelector("[data-sc-guard-error]");
    if (slot) {
        slot.textContent = message || "";
        slot.hidden = !message;
    }
}

async function save(form) {
    const { data, kinds } = fields(form);
    // URLSearchParams through scFetch takes one value per key: the kinds go
    // as repeated keys in the URL-encoded body instead.
    const body = new URLSearchParams();
    for (const [key, value] of Object.entries(data)) {
        body.set(key, value);
    }
    for (const kind of kinds) {
        body.append("kinds", kind);
    }
    form.dataset.scDashSaving = "1";
    setStatus(form, _t("Saving…"));
    try {
        const response = await fetch(form.action, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
            body,
        });
        const payload = await response.json().catch(() => null);
        if (!response.ok || !payload || !payload.ok) {
            setError(form, (payload && payload.error) || _t("This change could not be saved."));
            setStatus(form, "");
            return;
        }
        setError(form, "");
        setStatus(form, _t("Saved"));
        syncRow(form);
    } catch {
        setError(form, _t("No connection: this change was not saved."));
        setStatus(form, "");
    } finally {
        delete form.dataset.scDashSaving;
    }
}

/** The row's look follows its switch and title (no reload). */
function syncRow(form) {
    const item = form.closest("[data-sc-dash-item]");
    const toggle = form.querySelector('input[role="switch"][name="enabled"]');
    if (item && toggle) {
        item.classList.toggle("o_sc_dash_cfg_off", !toggle.checked);
    }
    const title = form.querySelector('input[name="title"]');
    const label = form.querySelector(".o_sc_dash_cfg_switch .o_sc_switch_label");
    if (title && label) {
        label.textContent = title.value.trim() || title.placeholder;
    }
}

function schedule(form, delay) {
    clearTimeout(timers.get(form));
    timers.set(form, setTimeout(() => save(form), delay));
}

document.addEventListener("change", (ev) => {
    const form = instanceForm(ev.target);
    if (!form) {
        return;
    }
    // A switch's « off » twin follows sc_switch.js (capture phase) first.
    schedule(form, ev.target.name === "title" ? 0 : 50);
});

document.addEventListener("input", (ev) => {
    const form = instanceForm(ev.target);
    if (form && ev.target.name === "title") {
        schedule(form, TITLE_DELAY);
    }
});

document.addEventListener("submit", (ev) => {
    const form = ev.target;
    if (instanceForm(form) === form) {
        ev.preventDefault();
        save(form);
        return;
    }
    if (form.matches && form.matches("form[data-sc-dash-reset-form]") && inApp(form)) {
        if (form.dataset.scDashConfirmed) {
            return;
        }
        ev.preventDefault();
        scConfirm({
            title: form.dataset.scConfirmTitle,
            message: form.dataset.scConfirmMessage,
            confirm: form.dataset.scConfirmOk,
            cancel: form.dataset.scConfirmCancel,
        }).then((ok) => {
            if (ok) {
                form.dataset.scDashConfirmed = "1";
                form.submit();
            }
        });
    }
});

function init() {
    for (const button of document.querySelectorAll(".o_sc_app [data-sc-dash-save]")) {
        button.hidden = true;
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
