// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {
  messageActionsRegistry,
  registerMessageAction,
} from "@mail/core/common/message_actions";
import {_t} from "@web/core/l10n/translation";
import {openReplyDialog} from "./reply_dialog";
import {replyTargets} from "./reply_thread_patch";

/** A message a correspondent has seen, on a conversation's own thread. */
function isReplyTarget({message, thread}) {
  return (
    thread?.model === "mail.conversation" &&
    message.thread?.eq(thread) &&
    typeof message.id === "number" &&
    (message.message_type === "email" || replyTargets.has(message.id))
  );
}

registerMessageAction("conversation-reply", {
  condition: isReplyTarget,
  icon: "fa fa-reply",
  name: _t("Reply"),
  onSelected: ({message, owner, thread}) =>
    openReplyDialog(owner.env, thread, message.id),
  sequence: 20,
});

// A message must never offer two actions labelled "Reply": where ours shows,
// the native one (the Log note composer) steps aside. Internal notes and every
// other model keep it.
const nativeReplyTo = messageActionsRegistry.get("reply-to");
messageActionsRegistry.add(
  "reply-to",
  {
    ...nativeReplyTo,
    condition: (component) =>
      !isReplyTarget(component) && nativeReplyTo.condition(component),
  },
  {force: true}
);
