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
 *
 * Review round 2 (owner 2026-10-29) — the three zones (left / right /
 * bottom, ol[data-sc-dash-zone]):
 * - laptop: drag a row by its handle ([data-sc-dash-drag]) within a zone or
 *   to another one — Odoo's sortable helper (@web/core/utils/sortable, set
 *   up without OWL as the « sortable » service does); the drop posts the
 *   zone and the position to /configure/move by fetch; a refusal puts the
 *   page back as it was (reload);
 * - « Move to » (form[data-sc-dash-zone-form]): picking a zone posts at
 *   once and moves the row to the end of that zone (no reload);
 * - after either, ▲ / ▼ follow (disabled at a zone's edges).
 */
import { _t } from "@web/core/l10n/translation";
import { reactive } from "@odoo/owl";
import { useSortable } from "@web/core/utils/sortable";
import { throttleForAnimation } from "@web/core/utils/timing";
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

// ------------------------------------------------------------------ zones
async function postMove(data) {
    const body = new URLSearchParams(data);
    const response = await fetch("/my/app/dashboard/configure/move", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
        body,
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload || !payload.ok) {
        throw new Error((payload && payload.error) || _t("This change could not be saved."));
    }
}

function csrf() {
    const input = document.querySelector('.o_sc_app [data-sc-dash-zones] input[name="csrf_token"]');
    return input ? input.value : "";
}

/** ▲ / ▼ and « Move to » follow each row's zone and place. */
function syncZones() {
    for (const list of document.querySelectorAll(".o_sc_app ol[data-sc-dash-zone]")) {
        const items = [...list.querySelectorAll(":scope > li[data-sc-dash-item]")];
        items.forEach((item, index) => {
            const up = item.querySelector('button[data-sc-dash-move="up"]');
            const down = item.querySelector('button[data-sc-dash-move="down"]');
            if (up) {
                up.disabled = index === 0;
            }
            if (down) {
                down.disabled = index === items.length - 1;
            }
            const select = item.querySelector("select[data-sc-dash-zone-select]");
            if (select) {
                select.value = list.dataset.scDashZone;
            }
        });
    }
}

function showMoveError(item, message) {
    const form = item && item.querySelector("form[data-sc-dash-instance]");
    if (form) {
        setError(form, message);
    }
}

document.addEventListener("change", (ev) => {
    const select = ev.target.closest && ev.target.closest("select[data-sc-dash-zone-select]");
    if (!select || !inApp(select)) {
        return;
    }
    const item = select.closest("li[data-sc-dash-item]");
    const zone = select.value;
    const target = document.querySelector(`.o_sc_app ol[data-sc-dash-zone="${zone}"]`);
    if (!item || !target) {
        return;
    }
    postMove({ csrf_token: csrf(), instance_id: item.dataset.scDashItem, zone })
        .then(() => {
            target.appendChild(item);
            syncZones();
            showMoveError(item, "");
            item.scrollIntoView({ block: "nearest" });
        })
        .catch((error) => {
            syncZones();
            showMoveError(item, error.message);
        });
});

function initSortable() {
    const root = document.querySelector(".o_sc_app [data-sc-dash-zones]");
    if (!root) {
        return;
    }
    const setups = new Map();
    const setupHooks = {
        wrapState: reactive,
        throttle: throttleForAnimation,
        addListener: (el, type, listener, options) => el.addEventListener(type, listener, options),
        setup: (setupFn, dependenciesFn) => setups.set(setupFn, dependenciesFn),
        teardown: () => {},
    };
    useSortable({
        setupHooks,
        ref: { el: root },
        elements: "li[data-sc-dash-item]",
        groups: "ol[data-sc-dash-zone]",
        connectGroups: true,
        handle: "[data-sc-dash-drag]",
        placeholderClasses: ["o_sc_dash_cfg_placeholder"],
        applyChangeOnDrop: true,
        onDrop: ({ element, parent, group }) => {
            // ``parent`` = the zone dropped into (``group`` is the one the
            // row came from); an empty zone gets the row appended (the
            // helper only moves it next to a sibling).
            const list = parent || group || element.parentElement;
            if (element.parentElement !== list) {
                list.appendChild(element);
            }
            const items = [...list.querySelectorAll(":scope > li[data-sc-dash-item]")];
            postMove({
                csrf_token: csrf(),
                instance_id: element.dataset.scDashItem,
                zone: list.dataset.scDashZone,
                position: String(items.indexOf(element)),
            })
                .then(() => {
                    syncZones();
                    root.dataset.scDashDropped = String(Number(root.dataset.scDashDropped || 0) + 1);
                })
                .catch(() => window.location.reload());
        },
    });
    for (const [setupFn, dependenciesFn] of setups) {
        setupFn(...dependenciesFn());
    }
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
    // « Move to » saves on pick: its no-JS « OK » goes.
    for (const button of document.querySelectorAll(".o_sc_app [data-sc-dash-zone-go]")) {
        button.hidden = true;
    }
    initSortable();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
