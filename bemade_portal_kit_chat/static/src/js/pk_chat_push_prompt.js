/*
 * Task 5546 — the one-time « get notified on this phone? » banner, in the
 * conversation the user just wrote in (after a message they sent).
 *
 * Shown only when the server says it is due (span[data-pk-chat-push-prompt]
 * in the client's texts: phone notifications available, the prompt never
 * answered) AND the installed app's script is there (window.pkPush, from
 * bemade_portal_kit_pwa, which this addon does not depend on) AND:
 * - the browser can, and has never been asked (permission « default »):
 *   [Turn on] [Later];
 * - an iPhone / iPad outside the installed app: the add-to-home-screen
 *   hint and [OK].
 * Either answer is remembered for the USER (pkPush.markPrompted(): it
 * never comes back, on any phone).
 */
export const PK_CHAT_PUSH_DONE = "pkChatPushDone";

function button(className, text, attr) {
    const node = document.createElement("button");
    node.type = "button";
    node.className = className;
    node.setAttribute(attr, "1");
    node.textContent = text;
    return node;
}

/**
 * Show the banner in ``thread`` (a ChatThread) when due. ``options``:
 * ``push`` (default window.pkPush), ``root`` (where the texts span is).
 * Resolves to the banner shown ("enable", "ios") or null.
 */
export async function pkChatPushPrompt(thread, { push = window.pkPush, root = document } = {}) {
    const spec = root.querySelector("[data-pk-chat-push-prompt]");
    if (!spec || spec.dataset[PK_CHAT_PUSH_DONE] || !push || !thread || !thread.root) {
        return null;
    }
    if (thread.root.querySelector("[data-pk-chat-push-banner]")) {
        return null;
    }
    let status;
    try {
        status = await push.status();
    } catch {
        return null;
    }
    let variant = null;
    if (status.state === "ios-install") {
        variant = "ios";
    } else if (status.state === "off" && status.permission === "default") {
        variant = "enable";
    }
    if (!variant) {
        return null;
    }
    const texts = spec.dataset;
    const banner = document.createElement("div");
    banner.className = "o_pk_chat_push_banner";
    banner.setAttribute("data-pk-chat-push-banner", variant);
    banner.setAttribute("role", "status");
    const text = document.createElement("p");
    text.textContent = variant === "ios" ? texts.pkChatPushIos : texts.pkChatPushAsk;
    const actions = document.createElement("div");
    actions.className = "o_pk_chat_push_actions";
    const done = () => {
        spec.dataset[PK_CHAT_PUSH_DONE] = "1";
        banner.remove();
        push.markPrompted().catch(() => {});
    };
    if (variant === "enable") {
        const on = button("o_pk_btn o_pk_btn_primary", texts.pkChatPushOn, "data-pk-chat-push-on");
        const later = button("o_pk_btn o_pk_btn_ghost", texts.pkChatPushLater, "data-pk-chat-push-later");
        // enable() asks the permission FIRST, inside this click (iOS).
        on.addEventListener("click", () => {
            const asked = push.enable();
            done();
            asked.catch(() => {});
        });
        later.addEventListener("click", done);
        actions.append(on, later);
    } else {
        actions.append(button("o_pk_btn o_pk_btn_ghost", texts.pkChatPushOk, "data-pk-chat-push-later"));
        actions.firstChild.addEventListener("click", done);
    }
    banner.append(text, actions);
    thread.root.insertBefore(banner, thread.form);
    return variant;
}
