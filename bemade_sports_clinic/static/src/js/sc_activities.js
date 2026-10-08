/*
 * Task 1539 (epic #1535) — activity sheets of the app shell.
 *
 * Replaces, FOR THE SHELL ONLY, the inline scripts of the legacy
 * activity_list_table / reassign modal / assignee warning (those partials
 * stay unchanged for the legacy pages). Progressive enhancement, inert
 * outside .o_sc_app:
 *
 * - a row action ([data-sc-activity-id] + data-sc-sheet-open) fills the
 *   opened sheet's form: activity_id, the current assignee's name
 *   ([data-sc-current-assignee]) and resets the new-assignee select;
 * - an assignee <select data-sc-assignee-select> shows the advisory
 *   « no access to this team » warning (task 1402) for the ids listed in
 *   its data-sc-no-access attribute.
 */
function inShell(el) {
    return Boolean(el && el.closest && el.closest(".o_sc_app"));
}

document.addEventListener("click", (ev) => {
    const opener = ev.target.closest && ev.target.closest("[data-sc-activity-id][data-sc-sheet-open]");
    if (!opener || !inShell(opener)) {
        return;
    }
    const sheet = document.getElementById(opener.dataset.scSheetOpen);
    if (!sheet) {
        return;
    }
    for (const input of sheet.querySelectorAll('input[name="activity_id"]')) {
        input.value = opener.dataset.scActivityId;
    }
    const current = sheet.querySelector("[data-sc-current-assignee]");
    if (current) {
        current.textContent = opener.dataset.scCurrentUser || "";
    }
    const select = sheet.querySelector('select[name="new_user_id"]');
    if (select) {
        select.value = "";
    }
});

function refreshAssigneeWarning(select) {
    const form = select.closest("form") || document;
    const warning = form.querySelector("[data-sc-assignee-warning]");
    if (!warning) {
        return;
    }
    const noAccess = (select.dataset.scNoAccess || "").split(/\s+/).filter(Boolean);
    warning.hidden = !noAccess.includes(select.value);
}

document.addEventListener("change", (ev) => {
    const select = ev.target;
    if (select instanceof HTMLSelectElement && select.dataset.scAssigneeSelect && inShell(select)) {
        refreshAssigneeWarning(select);
    }
});

function init() {
    for (const select of document.querySelectorAll(".o_sc_app select[data-sc-assignee-select]")) {
        refreshAssigneeWarning(select);
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
