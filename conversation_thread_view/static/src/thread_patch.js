// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {Thread} from "@mail/core/common/thread";
import {patch} from "@web/core/utils/patch";

/**
 * In the thread view the messages read like an email thread, oldest first by
 * their own date: a captured email keeps the date it was sent, which can be
 * older than the conversation's own creation record, so the stock order (by
 * id) would not be chronological. Everywhere else the stock thread is
 * untouched: the patch only acts where the thread view sets
 * ``env.conversationThreadView``.
 */
patch(Thread.prototype, {
  get orderedMessages() {
    const messages = super.orderedMessages;
    if (!this.env.conversationThreadView) {
      return messages;
    }
    const time = (message) => message.date?.ts ?? Infinity;
    return messages.sort((a, b) => time(a) - time(b) || a.id - b.id);
  },
});
