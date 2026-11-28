/*
 * Task 5566 — a CLOSED managed channel in Discuss (``pk_closed`` and
 * ``pk_closed_label`` come with the channel in the store, live through the
 * channel's sync fields): no composer (pk_chat_closed.xml), its chip in
 * the header, and no « Reply », « Edit », « Delete » or « Pin » on its
 * messages (pinning posts a notice, refused there), no new sub-thread and
 * no call.
 * The server refuses every write anyway (discuss_channel.py): this only
 * hides what would fail. Kept tiny (upgrade-fragile).
 */
import { messageActionsRegistry } from "@mail/core/common/message_actions";
// The « Pin » action is registered there: loaded first, so it can be wrapped.
import "@mail/discuss/message_pin/common/message_actions";
import { Message } from "@mail/core/common/message_model";
import { Thread } from "@mail/core/common/thread_model";
// Loaded first, so their getter can be wrapped.
import "@mail/discuss/core/public_web/thread_model_patch";
import { patch } from "@web/core/utils/patch";

/** Is ``thread`` a closed managed channel? (pure: the hoot test uses it) */
export function pkChatIsClosed(thread) {
    return Boolean(thread && thread.model === "discuss.channel" && thread.pk_closed);
}

patch(Message.prototype, {
    get editable() {
        return !pkChatIsClosed(this.thread) && super.editable;
    },
    canReplyTo(thread) {
        return !pkChatIsClosed(thread) && super.canReplyTo(thread);
    },
});

patch(Thread.prototype, {
    get hasSubChannelFeature() {
        return !pkChatIsClosed(this) && super.hasSubChannelFeature;
    },
    get allowCalls() {
        return !pkChatIsClosed(this) && super.allowCalls;
    },
});

if (messageActionsRegistry.contains("pin")) {
    const pin = messageActionsRegistry.get("pin");
    const condition = pin.condition;
    messageActionsRegistry.add(
        "pin",
        {
            ...pin,
            condition: (args) =>
                !pkChatIsClosed(args.thread) &&
                (typeof condition === "function" ? condition(args) : condition !== false),
        },
        { force: true }
    );
}
