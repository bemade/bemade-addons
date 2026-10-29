/*
 * Task 1624, review round 1 (owner 2026-10-29) — « Suivre / Ne plus suivre »
 * a player (template sc_follow_toggle: the player cards' « Details » and the
 * player page header). Inert outside .o_sc_app.
 *
 * The toggle is a small form posting to /my/player/<id>/follow (the no-JS
 * fallback). Here it is saved with fetch, no reload: on success every toggle
 * of that player on the page flips (a player may be listed in several
 * sections); on a refusal nothing moves (scFetch shows the error toast).
 */
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

function setFollowed(playerId, followed) {
    for (const button of document.querySelectorAll(`.o_sc_app [data-sc-follow="${playerId}"]`)) {
        button.dataset.scFollowed = followed ? "1" : "0";
        button.setAttribute("aria-pressed", followed ? "true" : "false");
        button.classList.toggle("o_sc_btn_primary", followed);
        button.classList.toggle("o_sc_btn_ghost", !followed);
        for (const label of button.querySelectorAll("[data-sc-follow-label]")) {
            label.hidden = (label.dataset.scFollowLabel === "on") !== followed;
        }
        const input = button.form && button.form.querySelector('input[name="follow"]');
        if (input) {
            input.value = followed ? "0" : "1";
        }
    }
}

document.addEventListener("submit", async (ev) => {
    const form = ev.target;
    if (!(form instanceof HTMLFormElement) || !form.classList.contains("o_sc_follow_form")
            || !form.closest(".o_sc_app")) {
        return;
    }
    ev.preventDefault();
    const button = form.querySelector("[data-sc-follow]");
    if (!button || button.disabled) {
        return;
    }
    const follow = button.dataset.scFollowed !== "1";
    button.disabled = true;
    try {
        const answer = await scFetch(form.getAttribute("action"), {
            method: "POST",
            data: { follow: follow ? "1" : "0" },
        });
        if (answer && answer.ok) {
            setFollowed(button.dataset.scFollow, Boolean(answer.followed));
        }
    } catch {
        // scFetch already showed the error toast; the toggle stays as is.
    } finally {
        button.disabled = false;
    }
});
