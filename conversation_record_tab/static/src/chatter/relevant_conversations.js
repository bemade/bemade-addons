// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {deserializeDateTime, formatDateTime} from "@web/core/l10n/dates";
import {onWillUnmount, useEffect, useState} from "@odoo/owl";
import {Chatter} from "@mail/chatter/web_portal/chatter";
import {KeepLast} from "@web/core/utils/concurrency";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";

// The conversation form has its own "Linked Records" page.
const EXCLUDED_MODELS = ["mail.conversation"];

patch(Chatter.prototype, {
  setup() {
    super.setup(...arguments);
    this.conversationOrm = useService("orm");
    this.conversationAction = useService("action");
    this.relevantKeepLast = new KeepLast();
    // The loadedFor key is "<model>,<id>" once the list for that record is
    // settled (loaded or skipped); it is rendered as an inert data attribute
    // on the chatter root.
    this.relevantConversations = useState({
      count: 0,
      scopes: [],
      open: true,
      loadedFor: false,
    });
    useEffect(
      (model, id) => {
        this.loadRelevantConversations(model, id);
      },
      () => [this.props.threadModel, this.props.threadId]
    );
    onWillUnmount(() => (this.relevantKeepLast = null));
  },

  async loadRelevantConversations(model, id) {
    const state = this.relevantConversations;
    state.count = 0;
    state.scopes = [];
    state.loadedFor = false;
    const recordKey = `${model},${id}`;
    if (!user.isInternalUser || !id || EXCLUDED_MODELS.includes(model)) {
      state.loadedFor = recordKey;
      return;
    }
    const keepLast = this.relevantKeepLast;
    const result = await keepLast.add(
      this.conversationOrm.call("mail.conversation.link", "get_record_conversations", [
        model,
        id,
      ])
    );
    if (this.relevantKeepLast !== keepLast) {
      return;
    }
    state.count = result.count;
    state.scopes = result.scopes;
    state.loadedFor = recordKey;
  },

  toggleRelevantConversations() {
    this.relevantConversations.open = !this.relevantConversations.open;
  },

  formatConversationDate(value) {
    return value ? formatDateTime(deserializeDateTime(value)) : "";
  },

  openRelevantConversation(conversationId) {
    this.conversationAction.doAction({
      type: "ir.actions.act_window",
      res_model: "mail.conversation",
      res_id: conversationId,
      views: [[false, "form"]],
      target: "current",
    });
  },
});
