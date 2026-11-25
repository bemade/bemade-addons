// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {Message} from "@mail/core/common/message";
import {patch} from "@web/core/utils/patch";
import {replyTargets} from "@conversation_draft/reply_thread_patch";

/**
 * Both patches only act where the thread view sets
 * ``env.conversationThreadView``; everywhere else the stock behaviour stays.
 */
patch(Message.prototype, {
  /**
   * In the thread view every message action is a visible button instead of
   * folding the last ones into a "..." menu, so Reply and Forward are always
   * one click away.
   */
  get quickActionCount() {
    if (this.env.conversationThreadView) {
      return 8;
    }
    return super.quickActionCount;
  },

  /**
   * An internal note: an in-app comment nobody outside saw. Captured inbound
   * mail is also recorded with the note subtype, so the messages a
   * correspondent has seen (the ones that offer Reply) are excluded, and so
   * are tracking and other system messages.
   */
  get isConversationInternalNote() {
    return Boolean(
      this.env.conversationThreadView &&
        this.message.isNote &&
        this.message.message_type === "comment" &&
        !replyTargets.has(this.message.id)
    );
  },

  /**
   * What the thread view shows this message as: ``mail`` (a message a
   * correspondent has seen), ``note`` (an internal note) or ``other`` (a
   * system record). Undefined outside the thread view. Exposed as a data
   * attribute so tours and demos can tell the messages apart.
   */
  get conversationThreadKind() {
    if (!this.env.conversationThreadView) {
      return undefined;
    }
    if (replyTargets.has(this.message.id)) {
      return "mail";
    }
    return this.isConversationInternalNote ? "note" : "other";
  },
});
