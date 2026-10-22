/*
 * Task 1652 — a player card's red allergy / medical-alert pill opens the
 * player page's popup (inert outside .o_sc_app).
 *
 * button[data-sc-med-card-sheet] sits inside the card (often its link or its
 * <summary>): the tap opens the page-level sheet it names (sc_app_layout
 * renders one set per player shown with a red pill, scope « card ») and
 * never follows the card's link nor toggles the card (capture phase). No
 * such sheet on the page (a player who turned red after the page loaded):
 * the player's Info tab, as before.
 */
document.addEventListener(
    "click",
    (ev) => {
        const pill = ev.target.closest && ev.target.closest("[data-sc-med-card-sheet]");
        if (!pill || !pill.closest(".o_sc_app")) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const dialog = document.getElementById(pill.dataset.scMedCardSheet || "");
        if (dialog && typeof dialog.showModal === "function") {
            // #1641: no focus left inside a read fragment for the dialog to
            // give back (the card would never refresh after an edit).
            pill.blur();
            if (!dialog.open) {
                dialog.showModal();
            }
        } else if (pill.dataset.scMedFallback) {
            window.location.assign(pill.dataset.scMedFallback);
        }
    },
    true
);
