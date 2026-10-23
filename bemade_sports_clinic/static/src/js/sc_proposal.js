/*
 * Task 1603 — follow-up proposals (inert outside .o_sc_app).
 *
 * A save may answer ``propose`` (controllers/app_shell.py, SAVE_REGISTRY
 * ``propose``; payload documented in models/patient_return_proposal.py):
 * {kind, patient_id, title, message, items: [{model, id, field, label,
 * current, proposed, current_display, proposed_display, editable, tickable,
 * checked}]}. The save itself is done — the proposal is a dismissable
 * follow-up. This module shows it in the layout's #sc_proposal_sheet:
 *
 * - each item is a row « label · current → proposed »; ``editable`` rows
 *   carry a date input (prefilled with the proposed date), ``tickable`` rows
 *   a checkbox (``checked`` by default);
 * - « Apply » posts the ticked rows to /my/app/apply-proposal
 *   ({patient_id, changes: JSON [{model, id, field, value}]}), which
 *   re-validates and writes them through the normal save paths; on success
 *   the sheet closes, each written field is announced as an « sc:saved »
 *   (the autosave islands and data-sc-display read views follow, the read
 *   fragments refresh — task 1611) and the toast confirms;
 * - « Dismiss », the close button, Escape or the backdrop: nothing written.
 *
 * Sources: an « sc:saved » whose result carries ``propose``; the
 * data-sc-proposal JSON a POST round-trip left on the sheet (shown on load);
 * the « sc:propose » DOM event ({detail: proposal}); or openProposal() from
 * other modules (task 1604's « Résoudre »).
 */
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

const APPLY_URL = "/my/app/apply-proposal";

function sheet() {
    return document.querySelector(".o_sc_app #sc_proposal_sheet");
}

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
        node.className = className;
    }
    if (text !== undefined && text !== null) {
        node.textContent = text;
    }
    return node;
}

function itemKey(item) {
    return `${item.model}:${item.id}:${item.field}`;
}

function buildRow(item) {
    const row = el("li", "o_sc_proposal_item");
    row.dataset.scProposalItem = itemKey(item);
    const head = el(item.tickable ? "label" : "div", "o_sc_proposal_head");
    if (item.tickable) {
        head.classList.add("o_sc_check");
        const box = el("input");
        box.type = "checkbox";
        box.checked = item.checked !== false;
        box.dataset.scProposalTick = "1";
        head.append(box);
    }
    head.append(el("span", "o_sc_proposal_label", item.label));
    row.append(head);
    const change = el("div", "o_sc_proposal_change");
    change.append(el("span", "o_sc_proposal_current", item.current_display || "—"));
    change.append(el("span", "o_sc_proposal_arrow", "→"));
    if (item.editable) {
        const input = el("input", "o_sc_input o_sc_proposal_date");
        input.type = "date";
        input.value = item.proposed || "";
        input.dataset.scProposalValue = "1";
        input.setAttribute("aria-label", item.label);
        change.append(input);
    } else {
        change.append(el("strong", "o_sc_proposal_proposed", item.proposed_display || "—"));
    }
    row.append(change);
    return row;
}

let current = null;

/** Show ``proposal`` in the sheet (replacing one already shown). */
export function openProposal(proposal) {
    const dialog = sheet();
    if (!dialog || !proposal || !Array.isArray(proposal.items) || !proposal.items.length) {
        return false;
    }
    current = proposal;
    dialog.dataset.scProposalKind = proposal.kind || "";
    dialog.querySelector("[data-sc-proposal-title]").textContent = proposal.title || "";
    dialog.querySelector("[data-sc-proposal-message]").textContent = proposal.message || "";
    dialog.querySelector("[data-sc-proposal-items]").replaceChildren(...proposal.items.map(buildRow));
    dialog.querySelector("[data-sc-proposal-error]").hidden = true;
    dialog.querySelector("[data-sc-proposal-apply]").disabled = false;
    if (!dialog.open && typeof dialog.showModal === "function") {
        dialog.showModal();
    }
    return true;
}

/** The changes the sheet would apply now (ticked rows, edited values). */
export function proposalChanges() {
    const dialog = sheet();
    if (!dialog || !current) {
        return [];
    }
    const changes = [];
    for (const item of current.items) {
        const row = [...dialog.querySelectorAll("[data-sc-proposal-item]")].find(
            (node) => node.dataset.scProposalItem === itemKey(item)
        );
        if (!row) {
            continue;
        }
        const box = row.querySelector("[data-sc-proposal-tick]");
        if (box && !box.checked) {
            continue;
        }
        const input = row.querySelector("[data-sc-proposal-value]");
        changes.push({
            model: item.model,
            id: item.id,
            field: item.field,
            value: input ? input.value : item.proposed || "",
        });
    }
    return changes;
}

function close() {
    const dialog = sheet();
    current = null;
    if (dialog && dialog.open) {
        dialog.close();
    }
}

/** Announce each written field like a save (islands, read views, fragments). */
function announce(result) {
    for (const entry of result.saved || []) {
        const shown = { value: entry.value, display: entry.display };
        document.dispatchEvent(
            new CustomEvent("sc:saved", {
                detail: {
                    model: entry.model,
                    recordId: entry.id,
                    field: entry.field,
                    result: {
                        ok: true,
                        write_date: entry.write_date,
                        value: entry.value,
                        display: entry.display,
                        also: { [entry.field]: shown },
                        refresh: result.refresh || [],
                        saved_at: result.saved_at,
                    },
                },
            })
        );
    }
}

export async function applyProposal() {
    const dialog = sheet();
    if (!dialog || !current) {
        return false;
    }
    const changes = proposalChanges();
    if (!changes.length) {
        close();
        return true;
    }
    const button = dialog.querySelector("[data-sc-proposal-apply]");
    const error = dialog.querySelector("[data-sc-proposal-error]");
    button.disabled = true;
    error.hidden = true;
    try {
        const result = await scFetch(APPLY_URL, {
            method: "POST",
            data: { patient_id: current.patient_id, changes: JSON.stringify(changes) },
            toast: false,
        });
        close();
        announce(result);
        if (result.message) {
            document.dispatchEvent(new CustomEvent("sc:toast", { detail: { message: result.message } }));
        }
        return true;
    } catch (err) {
        const message = err && err.payload && err.payload.message;
        if (message) {
            error.textContent = message;
        }
        error.hidden = false;
        button.disabled = false;
        return false;
    }
}

document.addEventListener("click", (ev) => {
    const dialog = sheet();
    if (!dialog || !dialog.contains(ev.target)) {
        return;
    }
    if (ev.target.closest("[data-sc-proposal-apply]")) {
        ev.preventDefault();
        applyProposal();
    } else if (ev.target.closest("[data-sc-proposal-dismiss]")) {
        ev.preventDefault();
        close();
    }
});

document.addEventListener("sc:saved", (ev) => {
    const result = ev.detail && ev.detail.result;
    if (result && result.propose) {
        openProposal(result.propose);
    }
});

document.addEventListener("sc:propose", (ev) => {
    openProposal(ev.detail);
});

function showPending() {
    const dialog = sheet();
    if (!dialog || !dialog.dataset.scProposal) {
        return;
    }
    let proposal = null;
    try {
        proposal = JSON.parse(dialog.dataset.scProposal);
    } catch {
        proposal = null;
    }
    delete dialog.dataset.scProposal;
    openProposal(proposal);
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showPending);
} else {
    showPending();
}
