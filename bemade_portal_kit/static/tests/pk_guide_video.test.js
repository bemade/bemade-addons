/*
 * Task 5200 (P5) — pk_guide_video: a guide video link (the kit's class
 * « o_pk_video » and, for the articles already stored, « o_fc_video »)
 * becomes an inline player when its same-origin attachment is a video;
 * anything else stays a link. Synthetic fixtures only.
 */
import { describe, expect, getFixture, mockFetch, test } from "@odoo/hoot";

import { pkIsVideo, pkUpgradeVideoLinks, pkVideoSource } from "@bemade_portal_kit/js/pk_guide_video";

function answers() {
    mockFetch((input, init) => {
        const url = String(input);
        expect(init.method).toBe("HEAD");
        const video = /\/web\/content\/(1|2)(\?|$)/.test(new URL(url, window.location.origin).pathname + "?");
        return new Response("", { status: 200, headers: { "Content-Type": video ? "video/mp4" : "text/plain" } });
    });
}

describe("pk_guide_video", () => {
    test("pkVideoSource: same-origin /web/content/<id> only", () => {
        const origin = window.location.origin;
        expect(pkVideoSource("/web/content/1", origin)).toBe("/web/content/1");
        expect(pkVideoSource(`${origin}/web/content/1?download=0`, origin)).toBe("/web/content/1?download=0");
        expect(pkVideoSource("https://other.example.com/web/content/1", origin)).toBe(null);
        expect(pkVideoSource("javascript:alert(1)", origin)).toBe(null);
        expect(pkVideoSource("/pk/t/page", origin)).toBe(null);
    });

    test("pkIsVideo: the HEAD answer's content type", async () => {
        answers();
        expect(await pkIsVideo("/web/content/1")).toBe(true);
        expect(await pkIsVideo("/web/content/9")).toBe(false);
    });

    test("both link classes become players; a text attachment or an unmarked link stays a link", async () => {
        answers();
        getFixture().innerHTML = `<div>
            <p><a class="o_pk_video" id="v_new" href="/web/content/1">Video</a></p>
            <p><a class="o_fc_video" id="v_old" href="/web/content/2">Video</a></p>
            <p><a class="o_pk_video" id="v_text" href="/web/content/9">Notes</a></p>
            <p><a id="v_plain" href="/web/content/1">Not marked</a></p>
            <div contenteditable="true"><a class="o_pk_video" id="v_edit" href="/web/content/1">Edited</a></div>
        </div>`;
        const root = getFixture();
        expect(await pkUpgradeVideoLinks(root)).toBe(2);
        for (const id of ["v_new", "v_old"]) {
            const link = root.querySelector(`#${id}`);
            const player = link.previousElementSibling;
            expect(player.tagName).toBe("VIDEO");
            expect(player.classList.contains("o_pk_video_player")).toBe(true);
            expect(player.controls).toBe(true);
            expect(player.hasAttribute("playsinline")).toBe(true);
            expect(link.hidden).toBe(true);
        }
        for (const id of ["v_text", "v_plain", "v_edit"]) {
            const link = root.querySelector(`#${id}`);
            expect(link.hidden).toBe(false);
            expect(link.previousElementSibling).toBe(null);
        }
        // Once per link.
        expect(await pkUpgradeVideoLinks(root)).toBe(0);
    });
});
