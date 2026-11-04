/*
 * Task 1583 — « Add to Team » confirms on the players list at once: the
 * pending session notification shows as the status toast on the next shell
 * page (tests/test_app_shell_session_toast_1583.py). Language-independent
 * triggers.
 */
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("sc_1583_add_to_team_toast", {
    steps: () => [
        {
            content: "An out-of-team player offers « Add to Team »",
            trigger: '[data-sc-row-locked] form[data-sc-action="players.add_to_team"] button[type="submit"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the list: the confirmation toast shows at once",
            trigger: '.o_sc_app .o_sc_toast[data-sc-toast-tone="success"]:not([hidden]):contains("Two")',
        },
        {
            content: "The toast payload was consumed (shown once)",
            trigger: ".o_sc_app .o_sc_toast:not([data-sc-notify])",
        },
        {
            content: "The player's row is now a link, no « Add to Team » left",
            trigger: '[data-sc-section="players.list"] a[href^="/my/player?player_id="]',
            run() {
                if (document.querySelector('form[data-sc-action="players.add_to_team"]')) {
                    throw new Error("the « Add to Team » form is still offered");
                }
            },
        },
    ],
});
