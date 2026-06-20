/* License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */
/**
 * Feature C -- live log viewer handoff.
 *
 * Hands the short-lived signed scope token (minted server-side, embedded in
 * the ``data-log-scope`` attribute) to the sidecar iframe via ``postMessage``
 * -- NOT via the iframe ``src`` / query string, so the token is never logged
 * by proxies. (The attribute is named ``data-log-scope`` rather than
 * ``...token`` because Odoo's website layer strips ``*token*`` attributes.)
 *
 * The target origin is derived from the configured sidecar URL
 * (``data-log-viewer-url``) so the token is posted to the sidecar's origin
 * ONLY -- never broadcast with ``"*"``. The sidecar verifies the token's HMAC
 * signature and expiry, then trusts only its ``ns`` + ``sel`` claims.
 */
(function () {
    "use strict";

    function targetOriginFrom(url) {
        try {
            return new URL(url).origin;
        } catch (e) {
            return null;
        }
    }

    function handoff(container) {
        var token = container.getAttribute("data-log-scope");
        var viewerUrl = container.getAttribute("data-log-viewer-url");
        var iframe = container.querySelector("iframe.o_herd_log_iframe");
        if (!token || !viewerUrl || !iframe) {
            return;
        }
        var targetOrigin = targetOriginFrom(viewerUrl);
        if (!targetOrigin) {
            return;
        }

        var post = function () {
            if (iframe.contentWindow) {
                iframe.contentWindow.postMessage(
                    { type: "herd-log-token", token: token },
                    targetOrigin
                );
            }
        };

        // The iframe may load before or after this script runs; post on load,
        // and also re-post if the sidecar asks for the token after it boots.
        iframe.addEventListener("load", post);
        window.addEventListener("message", function (event) {
            if (
                event.origin === targetOrigin &&
                event.data &&
                event.data.type === "herd-log-token-request"
            ) {
                post();
            }
        });
    }

    function init() {
        document
            .querySelectorAll(".o_herd_log_viewer")
            .forEach(handoff);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
