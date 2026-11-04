/*
 * Task 1648 — the type-to-filter single-select picker for link fields
 * (inert outside .o_sc_app).
 *
 * Progressive enhancement of a <select data-sc-picker>: the select stays the
 * form value (POST routes and the autosave unchanged; without JS it is the
 * plain select). The picker adds, right after it, a text box: typing lists
 * the options whose label matches — accent- and case-insensitive, every
 * typed word the start of a word of the label (the header search's rule,
 * #1650: app_search.sc_name_matches) —, « × » clears, ArrowDown / ArrowUp /
 * Enter / Escape on a laptop. A pick sets the select and fires its
 * « change » (the autosave saves, the narrowing follows).
 *
 * Narrowing between the link fields of one form ([data-sc-picker-scope], or
 * the closest form / edit view): data-sc-picker-key = team | player |
 * injury | event; player and event options carry data-sc-teams (ids),
 * injury options data-sc-player (id). A team narrows the players and
 * events, a player the injuries; clearing the parent widens them again; a
 * child whose value no longer fits is cleared, with a visible hint.
 *
 * Never focused on open (#1646); the list sits in the flow under the box so
 * a phone keyboard does not hide it.
 *
 * Task 1722: data-sc-picker-empty on the select keeps its empty option
 * (« À déterminer », « Toutes les organisations ») as a real choice: listed
 * first (when it matches the typed words) and shown in the box when chosen.
 */
import { _t, translationIsReady } from "@web/core/l10n/translation";

const MAX_SHOWN = 50;

export function scFold(text) {
    return String(text || "")
        .normalize("NFKD")
        .replace(/[̀-ͯ]/g, "")
        .toLowerCase();
}

export function scWords(text) {
    return scFold(text).match(/[\p{L}\p{N}_]+/gu) || [];
}

/** #1650's rule: every typed word starts a word of the label. */
export function scNameMatches(queryWords, label) {
    const tokens = scWords(label);
    return queryWords.every((word) => tokens.some((token) => token.startsWith(word)));
}

function scopeOf(select) {
    return (
        select.closest("[data-sc-picker-scope]") ||
        select.closest('[data-sc-edit-view="edit"]') ||
        select.closest("form") ||
        select.parentElement
    );
}

function pickerOf(select) {
    const next = select.nextElementSibling;
    return next && next.classList.contains("o_sc_picker") ? next : null;
}

function keepsEmpty(select) {
    return Boolean(select.dataset.scPickerEmpty);
}

function labelOf(select) {
    const option = select.selectedOptions && select.selectedOptions[0];
    if (option && !option.value && keepsEmpty(select)) {
        return option.textContent.trim();
    }
    return option && option.value ? option.textContent.trim() : "";
}

function allowed(option) {
    return !option.dataset.scPickerOut;
}

function render(select, picker, query) {
    const list = picker.querySelector(".o_sc_picker_list");
    const words = scWords(query);
    const matches = [...select.options].filter(
        (option) =>
            (option.value || (keepsEmpty(select) && option.textContent.trim())) &&
            allowed(option) &&
            (!words.length || scNameMatches(words, option.textContent))
    );
    list.replaceChildren();
    for (const [index, option] of matches.slice(0, MAX_SHOWN).entries()) {
        const item = document.createElement("li");
        item.setAttribute("role", "option");
        item.id = `${picker.id}_opt_${index}`;
        item.dataset.scPickerValue = option.value;
        item.className = "o_sc_picker_option";
        item.textContent = option.textContent.trim();
        if (option.value === select.value) {
            item.setAttribute("aria-selected", "true");
        }
        list.appendChild(item);
    }
    const more = picker.querySelector(".o_sc_picker_more");
    more.hidden = matches.length <= MAX_SHOWN;
    const none = picker.querySelector(".o_sc_picker_none");
    none.hidden = Boolean(matches.length);
    picker.dataset.scPickerActive = "-1";
}

function openList(select, picker, query = "") {
    const list = picker.querySelector(".o_sc_picker_list");
    render(select, picker, query);
    list.hidden = false;
    picker.querySelector(".o_sc_picker_input").setAttribute("aria-expanded", "true");
}

function closeList(picker, { restore = true } = {}) {
    const select = picker.previousElementSibling;
    picker.querySelector(".o_sc_picker_list").hidden = true;
    picker.querySelector(".o_sc_picker_more").hidden = true;
    picker.querySelector(".o_sc_picker_none").hidden = true;
    const input = picker.querySelector(".o_sc_picker_input");
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    if (restore && select) {
        input.value = labelOf(select);
    }
}

function choose(select, value) {
    if (select.value !== value) {
        select.value = value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    const picker = pickerOf(select);
    if (picker) {
        closeList(picker);
        picker.querySelector(".o_sc_picker_clear").hidden = !select.value;
    }
}

function highlight(picker, index) {
    const items = [...picker.querySelectorAll(".o_sc_picker_option")];
    if (!items.length) {
        return;
    }
    const next = Math.max(0, Math.min(items.length - 1, index));
    items.forEach((item, i) => item.classList.toggle("o_sc_picker_option_active", i === next));
    picker.dataset.scPickerActive = String(next);
    picker.querySelector(".o_sc_picker_input").setAttribute("aria-activedescendant", items[next].id);
    items[next].scrollIntoView({ block: "nearest" });
}

let counter = 0;

export function enhance(select) {
    if (!select || select.dataset.scPickerReady || !select.closest(".o_sc_app")) {
        return;
    }
    select.dataset.scPickerReady = "1";
    const picker = document.createElement("div");
    picker.className = "o_sc_picker";
    picker.id = `sc_picker_${++counter}`;
    const label = select.id && document.querySelector(`label[for="${select.id}"]`);
    picker.innerHTML = `
        <div class="o_sc_picker_box">
            <input type="text" class="o_sc_input o_sc_picker_input" autocomplete="off" spellcheck="false"
                   role="combobox" aria-autocomplete="list" aria-expanded="false"/>
            <button type="button" class="o_sc_icon_btn o_sc_picker_clear" hidden="hidden">×</button>
        </div>
        <ul class="o_sc_picker_list" role="listbox" hidden="hidden"></ul>
        <small class="o_sc_hint o_sc_picker_more" hidden="hidden"></small>
        <small class="o_sc_hint o_sc_picker_none" hidden="hidden"></small>
        <small class="o_sc_hint o_sc_picker_cleared" role="status" hidden="hidden"></small>`;
    const input = picker.querySelector(".o_sc_picker_input");
    input.setAttribute("aria-controls", `${picker.id}_list`);
    picker.querySelector(".o_sc_picker_list").id = `${picker.id}_list`;
    input.placeholder = _t("Type to search…");
    if (label) {
        input.setAttribute("aria-label", label.textContent.trim());
    }
    input.disabled = select.disabled;
    const clear = picker.querySelector(".o_sc_picker_clear");
    clear.setAttribute("aria-label", _t("Clear"));
    clear.title = _t("Clear");
    picker.querySelector(".o_sc_picker_more").textContent = _t("Keep typing to narrow the list.");
    picker.querySelector(".o_sc_picker_none").textContent = _t("No match");
    input.value = labelOf(select);
    clear.hidden = !select.value || select.disabled;
    select.classList.add("o_sc_picker_native");
    select.setAttribute("tabindex", "-1");
    select.setAttribute("aria-hidden", "true");
    select.after(picker);
}

export function enhanceAll(root = document) {
    for (const select of root.querySelectorAll(".o_sc_app select[data-sc-picker]")) {
        enhance(select);
    }
}

// ------------------------------------------------------------ narrowing
function siblingsOf(select, key) {
    return [...scopeOf(select).querySelectorAll(`select[data-sc-picker-key="${key}"]`)];
}

function narrow(child, test, hint) {
    let cleared = false;
    for (const option of child.options) {
        if (!option.value) {
            continue;
        }
        if (test(option)) {
            delete option.dataset.scPickerOut;
            option.hidden = false;
        } else {
            option.dataset.scPickerOut = "1";
            option.hidden = true;
            if (option.value === child.value) {
                cleared = true;
            }
        }
    }
    const picker = pickerOf(child);
    if (cleared) {
        choose(child, "");
    }
    if (picker) {
        const note = picker.querySelector(".o_sc_picker_cleared");
        note.hidden = !cleared;
        note.textContent = cleared ? hint : "";
        if (!cleared) {
            picker.querySelector(".o_sc_picker_input").value = labelOf(child);
        }
    }
}

function applyNarrowing(select) {
    const key = select.dataset.scPickerKey;
    const value = select.value;
    if (key === "team") {
        const inTeam = (option) => !value || (option.dataset.scTeams || "").split(",").includes(value);
        for (const child of [...siblingsOf(select, "player"), ...siblingsOf(select, "event")]) {
            narrow(child, inTeam, _t("Cleared: not in the chosen team."));
        }
    } else if (key === "player") {
        const ofPlayer = (option) => !value || option.dataset.scPlayer === value;
        for (const child of siblingsOf(select, "injury")) {
            narrow(child, ofPlayer, _t("Cleared: not one of the chosen player's injuries."));
        }
    }
}

// --------------------------------------------------------------- events
document.addEventListener("input", (ev) => {
    const input = ev.target;
    if (!input.classList || !input.classList.contains("o_sc_picker_input")) {
        return;
    }
    const picker = input.closest(".o_sc_picker");
    openList(picker.previousElementSibling, picker, input.value);
});

document.addEventListener("click", (ev) => {
    const target = ev.target;
    if (!target.closest) {
        return;
    }
    const option = target.closest(".o_sc_picker_option");
    if (option) {
        const picker = option.closest(".o_sc_picker");
        choose(picker.previousElementSibling, option.dataset.scPickerValue);
        return;
    }
    const clear = target.closest(".o_sc_picker_clear");
    if (clear) {
        const picker = clear.closest(".o_sc_picker");
        choose(picker.previousElementSibling, "");
        picker.querySelector(".o_sc_picker_input").value = "";
        return;
    }
    const input = target.closest(".o_sc_picker_input");
    if (input) {
        const picker = input.closest(".o_sc_picker");
        if (picker.querySelector(".o_sc_picker_list").hidden) {
            input.select();
            openList(picker.previousElementSibling, picker, "");
        }
        return;
    }
    for (const picker of document.querySelectorAll(".o_sc_picker")) {
        if (!picker.contains(target) && !picker.querySelector(".o_sc_picker_list").hidden) {
            closeList(picker);
        }
    }
});

document.addEventListener("keydown", (ev) => {
    const input = ev.target;
    if (!input.classList || !input.classList.contains("o_sc_picker_input")) {
        return;
    }
    const picker = input.closest(".o_sc_picker");
    const list = picker.querySelector(".o_sc_picker_list");
    const current = Number(picker.dataset.scPickerActive || -1);
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        if (list.hidden) {
            openList(picker.previousElementSibling, picker, "");
        }
        highlight(picker, current + (ev.key === "ArrowDown" ? 1 : -1));
    } else if (ev.key === "Enter" && !list.hidden) {
        ev.preventDefault();
        const items = picker.querySelectorAll(".o_sc_picker_option");
        const item = items[current >= 0 ? current : 0];
        if (item) {
            choose(picker.previousElementSibling, item.dataset.scPickerValue);
        }
    } else if (ev.key === "Escape" && !list.hidden) {
        ev.preventDefault();
        ev.stopPropagation();
        closeList(picker);
    }
});

// Review round 3 (owner 2026-10-27): a press on the list (an option, its
// scrollbar, the hints) or on « × » must not take the focus from the box.
// It used to: the box's focusout closed the list 150 ms later, so a press
// held longer than that (a normal trackpad / mouse click) released over a
// hidden list and the pick was lost — the field kept its former value. The
// focus now stays in the box and the pick lands on « click », however long
// the press (the tags field does the same: mousedown.prevent on its list).
document.addEventListener("mousedown", (ev) => {
    const target = ev.target;
    if (!target.closest) {
        return;
    }
    const picker = target.closest(".o_sc_picker");
    if (picker && !target.closest(".o_sc_picker_input") && picker.contains(document.activeElement)) {
        ev.preventDefault();
    }
});

// Leaving the box without a pick: back to the chosen value's label.
document.addEventListener("focusout", (ev) => {
    const input = ev.target;
    if (!input.classList || !input.classList.contains("o_sc_picker_input")) {
        return;
    }
    const picker = input.closest(".o_sc_picker");
    if (ev.relatedTarget && picker.contains(ev.relatedTarget)) {
        return;
    }
    setTimeout(() => {
        if (!picker.contains(document.activeElement)) {
            closeList(picker);
        }
    }, 150);
});

// The select's value changed (a pick, the autosave's answer, a reset).
document.addEventListener("change", (ev) => {
    const select = ev.target;
    if (!(select instanceof HTMLSelectElement) || !select.dataset.scPickerReady) {
        return;
    }
    const picker = pickerOf(select);
    if (picker) {
        picker.querySelector(".o_sc_picker_input").value = labelOf(select);
        picker.querySelector(".o_sc_picker_clear").hidden = !select.value || select.disabled;
    }
    applyNarrowing(select);
});

// Selects arrive late (OWL islands mount after load, fragments, lazy
// bodies): enhance whatever appears, then apply the narrowing once.
function boot(root) {
    enhanceAll(root);
    for (const select of (root.querySelectorAll ? root : document).querySelectorAll(
        '.o_sc_app select[data-sc-picker-key="team"], .o_sc_app select[data-sc-picker-key="player"]'
    )) {
        if (select.value && !select.dataset.scPickerNarrowed) {
            select.dataset.scPickerNarrowed = "1";
            applyNarrowing(select);
        }
    }
}

if (typeof document !== "undefined") {
    const start = () => {
        boot(document);
        const app = document.querySelector(".o_sc_app");
        if (app && window.MutationObserver) {
            let pending = false;
            new MutationObserver(() => {
                if (!pending) {
                    pending = true;
                    requestAnimationFrame(() => {
                        pending = false;
                        boot(document);
                    });
                }
            }).observe(app, { childList: true, subtree: true });
        }
    };
    // The picker's own labels are translated: wait for the terms.
    const domReady = new Promise((resolve) =>
        document.readyState === "loading"
            ? document.addEventListener("DOMContentLoaded", resolve)
            : resolve()
    );
    Promise.all([domReady, translationIsReady]).then(start);
}
