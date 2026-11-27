/*
 * Task 1624, owner UAT round 2 (2026-10-29) — the app dashboard (/my/home,
 * [data-pk-dashboard]) in the browser. Inert elsewhere.
 *
 * Task 5202 (kit P7): the scroll anchoring of the dashboard's fold-outs is
 * bemade_portal_kit_dashboard's (pk_dashboard_anchor.js). This file keeps
 * the quick « Retour prévu » of « Retours dépassés »: once saved, the
 * card's date follows and « Dépassé » goes (a past date is refused by the
 * field, #1727); the line counts refresh as read fragments.
 */
import { requestRefresh } from "@bemade_portal_kit/js/pk_fragments";

function dashboard() {
    return document.querySelector(".o_pk_app [data-pk-dashboard]");
}

// ------------------------------------------------ quick « Retour prévu »
document.addEventListener("pk:saved", (ev) => {
    const { model, recordId, field, result } = ev.detail || {};
    if (model !== "sports.patient" || field !== "predicted_return_date" || !result || !dashboard()) {
        return;
    }
    for (const holder of document.querySelectorAll(`.o_pk_app [data-sc-row-return-value="${recordId}"]`)) {
        const date = holder.querySelector("[data-sc-row-return-date]");
        if (date && result.display !== undefined) {
            date.textContent = result.display || "—";
        }
        // Saved = today or later (a past date is refused): no longer passed.
        holder.classList.remove("o_pk_overdue");
        for (const flag of holder.querySelectorAll(".o_pk_overdue_sep, .o_pk_overdue_flag")) {
            flag.remove();
        }
    }
    // The « À faire » counts follow (the card itself stays until the next
    // visit: the player leaves the line then).
    requestRefresh(["pk.dashboard:todo:*"]);
});
