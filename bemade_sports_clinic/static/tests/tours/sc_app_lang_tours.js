/*
 * Task 1588 — « Paramètres › Langue » (« Plus » until task 1606): the profile
 * language is the only source of truth in the app shell
 * (tests/test_app_shell_lang.py). Starts on « Paramètres »
 * as a fr_CA user. Language-independent triggers (html[lang], values).
 */
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("sc_1588_lang_switch", {
    steps: () => [
        {
            content: "« Paramètres » in French, FR pressed",
            trigger: 'html[lang="fr-CA"] #sc_language button[name="lang"][value="fr_CA"][aria-pressed="true"]',
        },
        {
            content: "Choose EN",
            trigger: '#sc_language button[name="lang"][value="en_US"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The page is now English, EN pressed",
            trigger: 'html[lang="en-US"] #sc_language:contains("Language") button[value="en_US"][aria-pressed="true"]',
        },
        {
            content: "Tamper the language cookie back to French, reload",
            trigger: 'html[lang="en-US"] .o_sc_app',
            run() {
                document.cookie = "frontend_lang=fr_CA; path=/";
                window.location.reload();
            },
            expectUnloadPage: true,
        },
        {
            content: "Still the profile language (English), cookie reset",
            trigger: 'html[lang="en-US"] #sc_language button[value="en_US"][aria-pressed="true"]',
            run() {
                if (!document.cookie.includes("frontend_lang=en_US")) {
                    throw new Error("frontend_lang cookie not reset: " + document.cookie);
                }
            },
        },
    ],
});
