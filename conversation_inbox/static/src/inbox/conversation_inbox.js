/** @odoo-module */

import {Component, onWillStart, useState} from "@odoo/owl";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

/**
 * The in-Odoo GTD inbox/triage viewer (task #3965, AC5/AC6).
 *
 * Ingest-on-action: this component only ever reads through the
 * `browsable` transport's `browse_page`/`fetch_envelope` RPCs -- it
 * never persists anything itself. Every GTD action (capture/reassign/
 * reply/forward/route-via-alias/hide/archive/delete/mark-read) is a distinct, explicit server
 * call the human triggers; simply viewing a page never files anything.
 */
export class ConversationInboxAction extends Component {
  static template = "conversation_inbox.Inbox";

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.notification = useService("notification");
    this.dialog = useService("dialog");

    this.state = useState({
      transports: [],
      transportId: null,
      items: [],
      page: 1,
      hasMore: false,
      loading: false,
      expandedId: null,
      expandedBody: null,
      expandedAttachments: [],
    });

    onWillStart(async () => {
      await this.loadTransports();
      if (this.state.transportId) {
        await this.loadPage(1);
      }
    });
  }

  get currentTransport() {
    return this.state.transports.find((t) => t.id === this.state.transportId);
  }

  /**
   * A UserError (or any Odoo RPCError) must surface its OWN message, not
   * the generic top-level "Odoo Server Error" the JSON-RPC envelope
   * always carries (task #3965, blocking issue #1's error-rendering
   * fix): `error.data.message` is where Odoo actually puts the
   * exception's own text (`exception_to_unicode(exc)` server-side);
   * `error.message` is just the constant envelope label. Prefer the
   * former, and only fall back to the latter/a String() coercion for a
   * non-RPC error (e.g. a network failure) that never had a `.data`.
   */
  _errorMessage(error) {
    return (
      (error && error.data && error.data.message) || error.message || String(error)
    );
  }

  async loadTransports() {
    // Own + shared transports are already scoped server-side by the
    // conversation_transport ir.rule; the viewer surface only ever
    // shows browsable ones (AC5).
    const transports = await this.orm.searchRead(
      "conversation.transport",
      [["browsable", "=", true]],
      ["id", "name", "sendable", "mailbox_writable"]
    );
    this.state.transports = transports;
    this.state.transportId = transports.length ? transports[0].id : null;
  }

  async onTransportChange(ev) {
    this.state.transportId = ev.target.value ? parseInt(ev.target.value, 10) : null;
    this.state.expandedId = null;
    this.state.expandedBody = null;
    if (this.state.transportId) {
      await this.loadPage(1);
    } else {
      this.state.items = [];
    }
  }

  async loadPage(page) {
    if (!this.state.transportId) {
      return;
    }
    this.state.loading = true;
    try {
      const result = await this.orm.call("conversation.transport", "browse_page", [
        this.state.transportId,
        false,
        page,
      ]);
      this.state.items = result.items || [];
      this.state.page = result.page || page;
      this.state.hasMore = Boolean(result.has_more);
      this.state.expandedId = null;
      this.state.expandedBody = null;
      this.state.expandedAttachments = [];
    } catch (error) {
      this.notification.add(this._errorMessage(error), {type: "danger"});
    } finally {
      this.state.loading = false;
    }
  }

  async onNextPage() {
    if (this.state.hasMore) {
      await this.loadPage(this.state.page + 1);
    }
  }

  async onPrevPage() {
    if (this.state.page > 1) {
      await this.loadPage(this.state.page - 1);
    }
  }

  async onExpand(item) {
    if (this.state.expandedId === item.external_id) {
      this.state.expandedId = null;
      this.state.expandedBody = null;
      this.state.expandedAttachments = [];
      return;
    }
    this.state.expandedId = item.external_id;
    this.state.expandedBody = null;
    this.state.expandedAttachments = [];
    try {
      const envelope = await this.orm.call("conversation.transport", "fetch_envelope", [
        this.state.transportId,
        item.external_id,
      ]);
      this.state.expandedBody = envelope.body || "";
      this.state.expandedAttachments = envelope.attachments || [];
    } catch (error) {
      this.notification.add(this._errorMessage(error), {type: "danger"});
    }
  }

  /** Common context every GTD dialog wizard needs to identify the item. */
  _wizardContext(item, extra = {}) {
    return {
      default_transport_id: this.state.transportId,
      default_external_id: item.external_id,
      default_subject: item.subject,
      ...extra,
    };
  }

  async onCapture(item, mode) {
    await this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "conversation.inbox.capture.wizard",
      views: [[false, "form"]],
      target: "new",
      context: this._wizardContext(item, {default_mode: mode}),
    });
  }

  async onReassign(item) {
    await this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "conversation.inbox.reassign.wizard",
      views: [[false, "form"]],
      target: "new",
      context: this._wizardContext(item),
    });
  }

  async onCompose(item, actionType) {
    await this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "conversation.inbox.reply.wizard",
      views: [[false, "form"]],
      target: "new",
      context: this._wizardContext(item, {default_action_type: actionType}),
    });
  }

  async onRouteViaAlias(item) {
    try {
      await this.orm.call("mail.conversation", "action_route_via_alias", [
        this.state.transportId,
        item.external_id,
      ]);
      this.notification.add(_t("Routed through the alias gateway."), {
        type: "success",
      });
    } catch (error) {
      this.notification.add(this._errorMessage(error), {type: "danger"});
    }
  }

  /** Drop a row from the list and collapse it, without touching the server. */
  _removeItem(item) {
    this.state.items = this.state.items.filter(
      (candidate) => candidate.external_id !== item.external_id
    );
    if (this.state.expandedId === item.external_id) {
      this.state.expandedId = null;
      this.state.expandedBody = null;
      this.state.expandedAttachments = [];
    }
  }

  /**
   * Hide: remove the row from the list only. The message stays in the real
   * mailbox and returns on the next browse (an already-filed conversation
   * is archived server-side). Distinct from Archive/Delete, which act on
   * the mailbox itself.
   */
  async onHide(item) {
    try {
      await this.orm.call("mail.conversation", "action_dismiss", [
        this.state.transportId,
        item.external_id,
      ]);
      this._removeItem(item);
    } catch (error) {
      this.notification.add(this._errorMessage(error), {type: "danger"});
    }
  }

  /** Archive on the real mailbox, then drop the row. */
  async onArchive(item) {
    try {
      await this.orm.call("conversation.transport", "archive_item", [
        this.state.transportId,
        item.external_id,
      ]);
      this._removeItem(item);
    } catch (error) {
      this.notification.add(this._errorMessage(error), {type: "danger"});
    }
  }

  /** Move to the mailbox's Trash (recoverable) after an explicit confirm. */
  onDelete(item) {
    this.dialog.add(ConfirmationDialog, {
      title: _t("Delete message"),
      body: _t(
        "Move this message to the Trash of your mailbox? You can recover it from there."
      ),
      confirmLabel: _t("Delete"),
      cancelLabel: _t("Cancel"),
      confirm: async () => {
        try {
          await this.orm.call("conversation.transport", "trash_item", [
            this.state.transportId,
            item.external_id,
          ]);
          this._removeItem(item);
        } catch (error) {
          this.notification.add(this._errorMessage(error), {type: "danger"});
        }
      },
      // Passing `cancel` is what makes the dialog show a Cancel button.
      cancel: () => {
        // Cancelling makes no server call.
      },
    });
  }

  /** Set \Seen on the real mailbox; the row stays in the list. */
  async onMarkRead(item) {
    try {
      await this.orm.call("conversation.transport", "mark_read_item", [
        this.state.transportId,
        item.external_id,
      ]);
      this.notification.add(_t("Marked as read."), {type: "success"});
    } catch (error) {
      this.notification.add(this._errorMessage(error), {type: "danger"});
    }
  }
}

registry.category("actions").add("conversation_inbox", ConversationInboxAction);
