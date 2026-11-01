// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {Message} from "@mail/core/common/message";
import {patch} from "@web/core/utils/patch";

/**
 * A reply posted on a conversation notifies the conversation's internal
 * members in-app, so the message carries notifications even though nothing
 * went wrong: stock Odoo then draws an envelope announced as "Delivery
 * failure" next to it. Only that case is hidden. A message that really
 * failed (exception / bounce) keeps the stock indicator, and so does every
 * message of every other model.
 */
patch(Message.prototype, {
  get hideConversationDeliveryIcon() {
    const thread = this.message.thread;
    return Boolean(
      thread &&
        thread.model === "mail.conversation" &&
        !this.message.failureNotifications.length
    );
  },
});
