/** @odoo-module */

import {Component, markup, onWillStart, useState} from "@odoo/owl";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

// The existing per-item RPCs behind Hide / Archive / Delete / Mark read.
const ITEM_RPCS = {
  hide: ["mail.conversation", "action_dismiss"],
  archive: ["conversation.transport", "archive_item"],
  trash: ["conversation.transport", "trash_item"],
  mark_read: ["conversation.transport", "mark_read_item"],
};

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
      // What is typed in the search box, vs. the term the list was last
      // loaded with ("" = the normal inbox). Paging follows the latter.
      searchTerm: "",
      activeQuery: "",
      expandedId: null,
      expandedBody: null,
      expandedAttachments: [],
      // External_ids ticked for a bulk action. Only ever holds ids of rows
      // on the current page of the current account.
      selectedIds: [],
      bulkBusy: false,
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
      ["id", "name", "sendable", "mailbox_writable", "can_trash_mail", "searchable"]
    );
    this.state.transports = transports;
    this.state.transportId = transports.length ? transports[0].id : null;
  }

  /** Open the self-service "My mailboxes" screen (empty-state call to action). */
  onAddMailbox() {
    return this.action.doAction("conversation_inbox.conversation_transport_action_my");
  }

  async onTransportChange(ev) {
    this.state.transportId = ev.target.value ? parseInt(ev.target.value, 10) : null;
    this.state.expandedId = null;
    this.state.expandedBody = null;
    this.state.selectedIds = [];
    this.state.searchTerm = "";
    this.state.activeQuery = "";
    if (this.state.transportId) {
      await this.loadPage(1, "");
    } else {
      this.state.items = [];
    }
  }

  /**
   * Load one page of the normal inbox (`query` empty) or of the search
   * results for `query`. The query is the plain text the user typed:
   * the server turns it into a safe mailbox search, so nothing here
   * builds search syntax. `activeQuery` only moves once the call
   * succeeded, so a failed search leaves the previous list and its
   * paging intact.
   */
  async loadPage(page, query = this.state.activeQuery) {
    if (!this.state.transportId) {
      return;
    }
    const requestId = (this._requestId = (this._requestId || 0) + 1);
    this.state.loading = true;
    try {
      const result = await this.orm.call("conversation.transport", "browse_page", [
        this.state.transportId,
        query || false,
        page,
      ]);
      if (requestId !== this._requestId) {
        // A newer request superseded this one.
        return;
      }
      this.state.items = result.items || [];
      this.state.page = result.page || page;
      this.state.hasMore = Boolean(result.has_more);
      this.state.activeQuery = query || "";
      this.state.selectedIds = [];
      this.state.expandedId = null;
      this.state.expandedBody = null;
      this.state.expandedAttachments = [];
    } catch (error) {
      if (requestId === this._requestId) {
        this.notification.add(this._errorMessage(error), {type: "danger"});
      }
    } finally {
      if (requestId === this._requestId) {
        this.state.loading = false;
      }
    }
  }

  get canSearch() {
    const transport = this.currentTransport;
    return Boolean(transport && transport.searchable);
  }

  /** Enter / the magnifier: search the mailbox for the trimmed term. */
  async onSearchSubmit(ev) {
    if (ev) {
      ev.preventDefault();
    }
    const term = (this.state.searchTerm || "").trim();
    if (!term) {
      await this.onSearchClear();
      return;
    }
    this.state.searchTerm = term;
    await this.loadPage(1, term);
  }

  /** Back to page 1 of the normal inbox list. */
  async onSearchClear() {
    this.state.searchTerm = "";
    this.state.activeQuery = "";
    await this.loadPage(1, "");
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
      // The body is the only envelope field rendered as HTML, and only
      // because fetch_envelope returns it through conversation_base's
      // strict display sanitizer (tools/display.py). Subject, sender,
      // date and attachment names stay plain text that t-esc escapes.
      this.state.expandedBody = markup(envelope.body || "");
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
    try {
      const result = await this.orm.call(
        "conversation.inbox.capture.wizard",
        "action_open_for_item",
        [this.state.transportId, item.external_id, item.subject, mode]
      );
      await this.action.doAction(result);
    } catch (error) {
      this.notification.add(this._errorMessage(error), {type: "danger"});
    }
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

  /** Swallow a click so it never reaches the row's expand/collapse handler. */
  noop() {
    // Intentionally empty: `t-on-click.stop` does the work.
  }

  /** Drop a row from the list and collapse it, without touching the server. */
  _removeItem(item) {
    this.state.items = this.state.items.filter(
      (candidate) => candidate.external_id !== item.external_id
    );
    this.state.selectedIds = this.state.selectedIds.filter(
      (id) => id !== item.external_id
    );
    if (this.state.expandedId === item.external_id) {
      this.state.expandedId = null;
      this.state.expandedBody = null;
      this.state.expandedAttachments = [];
    }
  }

  // ------------------------------------------------------------------
  // Actions offered on every row, collapsed or not. None of them needs
  // the message body on the client: the dialogs and the alias routing
  // fetch the message server-side, and only when they need it.
  // ------------------------------------------------------------------

  /** The row's action icons, under the transport's own gating. */
  get rowActions() {
    const transport = this.currentTransport || {};
    const actions = [
      {
        key: "new_conversation",
        icon: "fa-plus-circle",
        label: _t("New Conversation"),
        title: _t("File this message as a new conversation"),
        run: (item) => this.onCapture(item, "new"),
      },
      {
        key: "add_existing",
        icon: "fa-comments-o",
        label: _t("Add to Existing"),
        title: _t("Add this message to an existing conversation"),
        run: (item) => this.onCapture(item, "existing"),
      },
      {
        key: "link_record",
        icon: "fa-link",
        label: _t("Link to Record"),
        title: _t("Link this message to a record in Odoo"),
        run: (item) => this.onCapture(item, "link"),
      },
      {
        key: "reassign",
        icon: "fa-user-plus",
        label: _t("Reassign"),
        title: _t("File this message and assign it to a colleague or a team"),
        run: (item) => this.onReassign(item),
      },
    ];
    if (transport.sendable) {
      actions.push(
        {
          key: "reply",
          icon: "fa-reply",
          label: _t("Reply"),
          title: _t("Reply to the sender"),
          run: (item) => this.onCompose(item, "reply"),
        },
        {
          key: "reply_all",
          icon: "fa-reply-all",
          label: _t("Reply All"),
          title: _t("Reply to the sender and everyone else on the message"),
          run: (item) => this.onCompose(item, "reply_all"),
        },
        {
          key: "forward",
          icon: "fa-share",
          label: _t("Forward"),
          title: _t("Forward this message to someone else"),
          run: (item) => this.onCompose(item, "forward"),
        }
      );
    }
    actions.push({
      key: "route_alias",
      icon: "fa-random",
      label: _t("Route via Alias"),
      title: _t("Route this message through the mail alias gateway"),
      run: (item) => this.onRouteViaAlias(item),
    });
    if (transport.mailbox_writable) {
      actions.push(
        {
          key: "mark_read",
          icon: "fa-envelope-open-o",
          label: _t("Mark read"),
          title: _t("Mark as read in your mailbox"),
          run: (item) => this.onMarkRead(item),
        },
        {
          key: "archive",
          icon: "fa-archive",
          label: _t("Archive"),
          title: _t("Archive in your mailbox"),
          run: (item) => this.onArchive(item),
        }
      );
      if (transport.can_trash_mail) {
        actions.push({
          key: "delete",
          icon: "fa-trash",
          label: _t("Delete"),
          title: _t("Move to the Trash of your mailbox"),
          danger: true,
          run: (item) => this.onDelete(item),
        });
      }
    }
    actions.push({
      key: "hide",
      icon: "fa-eye-slash",
      label: _t("Hide"),
      title: _t("Remove from this list only; the message stays in your mailbox."),
      run: (item) => this.onHide(item),
    });
    return actions;
  }

  /** The bulk bar's actions: only the ones that need no dialog input. */
  get bulkActions() {
    const transport = this.currentTransport || {};
    const actions = [];
    if (transport.mailbox_writable) {
      actions.push(
        {
          key: "mark_read",
          icon: "fa-envelope-open-o",
          label: _t("Mark selection as read"),
          title: _t("Mark the selected messages as read in your mailbox"),
          run: () => this.onBulkMarkRead(),
        },
        {
          key: "archive",
          icon: "fa-archive",
          label: _t("Archive selection"),
          title: _t("Archive the selected messages in your mailbox"),
          run: () => this.onBulkArchive(),
        }
      );
      if (transport.can_trash_mail) {
        actions.push({
          key: "delete",
          icon: "fa-trash",
          label: _t("Delete selection"),
          title: _t("Move the selected messages to the Trash of your mailbox"),
          danger: true,
          run: () => this.onBulkDelete(),
        });
      }
    }
    actions.push({
      key: "hide",
      icon: "fa-eye-slash",
      label: _t("Hide selection"),
      title: _t(
        "Remove the selected messages from this list only; they stay in your mailbox."
      ),
      run: () => this.onBulkHide(),
    });
    return actions;
  }

  // ------------------------------------------------------------------
  // Per-item server calls, shared by the row buttons and the bulk bar.
  // Each is one existing RPC taking (transport_id, external_id), so no
  // message body is ever fetched to run them.
  // ------------------------------------------------------------------

  _callItem(kind, item, transportId = this.state.transportId) {
    const [model, method] = ITEM_RPCS[kind];
    return this.orm.call(model, method, [transportId, item.external_id]);
  }

  /**
   * Hide: remove the row from the list only. The message stays in the real
   * mailbox and returns on the next browse (an already-filed conversation
   * is archived server-side). Distinct from Archive/Delete, which act on
   * the mailbox itself.
   */
  async onHide(item) {
    try {
      await this._callItem("hide", item);
      this._removeItem(item);
    } catch (error) {
      this.notification.add(this._errorMessage(error), {type: "danger"});
    }
  }

  /** Archive on the real mailbox, then drop the row. */
  async onArchive(item) {
    try {
      await this._callItem("archive", item);
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
          await this._callItem("trash", item);
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
      await this._callItem("mark_read", item);
      this.notification.add(_t("Marked as read."), {type: "success"});
    } catch (error) {
      this.notification.add(this._errorMessage(error), {type: "danger"});
    }
  }

  // ------------------------------------------------------------------
  // Selection and bulk actions.
  // ------------------------------------------------------------------

  isSelected(item) {
    return this.state.selectedIds.includes(item.external_id);
  }

  get allSelected() {
    return (
      this.state.items.length > 0 &&
      this.state.items.every((item) => this.isSelected(item))
    );
  }

  get selectedCountLabel() {
    return _t("%(count)s selected", {count: this.state.selectedIds.length});
  }

  toggleSelected(item) {
    this.state.selectedIds = this.isSelected(item)
      ? this.state.selectedIds.filter((id) => id !== item.external_id)
      : [...this.state.selectedIds, item.external_id];
  }

  /** The header checkbox: every row of this page, or none. */
  toggleSelectAll() {
    this.state.selectedIds = this.allSelected
      ? []
      : this.state.items.map((item) => item.external_id);
  }

  clearSelection() {
    this.state.selectedIds = [];
  }

  /**
   * Run one per-item RPC for exactly the ticked rows of this page, one
   * after the other. A failure never stops the remaining rows: it is
   * collected and reported once at the end, and the failed rows stay in
   * the list and stay ticked. Returns the number of successes.
   */
  async _bulkRun(kind) {
    const transportId = this.state.transportId;
    const items = this.state.items.filter((item) => this.isSelected(item));
    if (!items.length || this.state.bulkBusy) {
      return;
    }
    this.state.bulkBusy = true;
    const errors = [];
    let done = 0;
    try {
      for (const item of items) {
        try {
          await this._callItem(kind, item, transportId);
          done += 1;
          if (kind !== "mark_read") {
            this._removeItem(item);
          }
        } catch (error) {
          errors.push(this._errorMessage(error));
        }
      }
    } finally {
      this.state.bulkBusy = false;
    }
    if (errors.length) {
      this.notification.add(
        _t("%(failed)s of %(total)s messages failed: %(errors)s", {
          failed: errors.length,
          total: items.length,
          errors: [...new Set(errors)].join(" "),
        }),
        {type: "danger"}
      );
    } else if (kind === "mark_read") {
      this.notification.add(_t("Marked as read: %(count)s.", {count: done}), {
        type: "success",
      });
    }
  }

  onBulkHide() {
    return this._bulkRun("hide");
  }

  onBulkArchive() {
    return this._bulkRun("archive");
  }

  onBulkMarkRead() {
    return this._bulkRun("mark_read");
  }

  onBulkDelete() {
    const count = this.state.selectedIds.length;
    if (!count) {
      return;
    }
    this.dialog.add(ConfirmationDialog, {
      title: _t("Delete messages"),
      body:
        count === 1
          ? _t(
              "Move this message to the Trash of your mailbox? You can recover it from there."
            )
          : _t(
              "Move %(count)s messages to the Trash of your mailbox? You can recover them from there.",
              {count}
            ),
      confirmLabel: _t("Delete"),
      cancelLabel: _t("Cancel"),
      confirm: () => this._bulkRun("trash"),
      cancel: () => {
        // Cancelling makes no server call.
      },
    });
  }
}

registry.category("actions").add("conversation_inbox", ConversationInboxAction);
