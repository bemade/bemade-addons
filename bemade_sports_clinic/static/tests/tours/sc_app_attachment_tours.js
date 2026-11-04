/*
 * Task 1586 — an activity's attachment row is a download link to
 * /my/activity/<activity>/attachment/<attachment>; following it answers the
 * file (tests/test_activity_attachment_download.py). Language-independent
 * triggers.
 */
import { registry } from "@web/core/registry";

const ROW = "a.o_sc_entity_row[data-sc-attachment][download]";

registry.category("web_tour.tours").add("sc_1586_attachment_download", {
    steps: () => [
        {
            content: "The attachment row is a download link to the activity's attachment route",
            trigger: ROW,
            async run() {
                const link = document.querySelector(ROW);
                const href = link.getAttribute("href");
                if (!/^\/my\/activity\/\d+\/attachment\/\d+$/.test(href)) {
                    throw new Error(`href is « ${href} »`);
                }
                const resp = await fetch(href, { credentials: "same-origin" });
                if (resp.status !== 200) {
                    throw new Error(`download answered ${resp.status}`);
                }
                const disposition = resp.headers.get("Content-Disposition") || "";
                if (!disposition.startsWith("attachment")) {
                    throw new Error(`Content-Disposition is « ${disposition} »`);
                }
                const body = await resp.text();
                if (!body.startsWith("synthetic attachment payload 1586")) {
                    throw new Error("unexpected file content");
                }
                document.body.dataset.scTour1586 = "ok";
            },
        },
        {
            content: "Downloaded",
            trigger: "body[data-sc-tour1586=ok]",
        },
    ],
});
