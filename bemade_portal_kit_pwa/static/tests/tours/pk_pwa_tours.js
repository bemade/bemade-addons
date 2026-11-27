/*
 * Task 5201 (kit P6) — browser tours of the installable app (moved from
 * the first consumer's sc_1542_install_page / sc_1542_sw_kill_switch). Run
 * by tests/test_pk_pwa_tours.py; language-independent triggers only.
 */
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

tours.add("pk_pwa_install_page", {
    steps: () => [
        { trigger: '[data-pk-install-steps="ios"]' },
        { trigger: '[data-pk-install-steps="android"]' },
        { trigger: '[data-pk-install-steps="desktop"]' },
        {
            content: "Not installed in the test browser: no « installed » state",
            trigger: '[data-pk-install-state="installed"]:not(:visible)',
        },
    ],
});

tours.add("pk_pwa_sw_kill_switch", {
    steps: () => [
        {
            content: "Switch on: the shell registers the service worker (scope /)",
            trigger: 'html[data-pk-sw="registered"]',
            timeout: 20000,
            async run() {
                const regs = await navigator.serviceWorker.getRegistrations();
                const scopes = regs.map((reg) => new URL(reg.scope).pathname);
                assert(scopes.includes("/"), `scopes: ${scopes.join(", ")}`);
            },
        },
        {
            content: "An older device also holds a /my/ registration of the same worker",
            trigger: 'html[data-pk-sw="registered"]',
            async run() {
                const reg = await navigator.serviceWorker.register("/my/service-worker.js", {
                    scope: "/my/",
                });
                for (let i = 0; i < 100 && !reg.active; i++) {
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
                const regs = await navigator.serviceWorker.getRegistrations();
                assert(regs.length === 2, `registrations: ${regs.length}`);
                const keys = await caches.keys();
                assert(
                    keys.some((key) => key.startsWith("pk-app-shell-")),
                    `caches: ${keys.join(", ")}`
                );
            },
        },
        {
            content: "Turn the switch OFF",
            trigger: 'html[data-pk-sw="registered"]',
            async run() {
                await rpc("/web/dataset/call_kw/ir.config_parameter/set_param", {
                    model: "ir.config_parameter",
                    method: "set_param",
                    args: ["bemade_portal_kit.enabled", false],
                    kwargs: {},
                });
                window.location.assign("/my");
            },
            expectUnloadPage: true,
        },
        {
            content: "Stock portal page: the worker answers 404 -> EVERY registration removed",
            trigger: 'html[data-pk-sw="unregistered"]:not(:has(.o_pk_app))',
            timeout: 20000,
            async run() {
                const regs = await navigator.serviceWorker.getRegistrations();
                assert(regs.length === 0, `registrations left: ${regs.length}`);
            },
        },
    ],
});
