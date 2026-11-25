// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {listView} from "@web/views/list/list_view";
import {registry} from "@web/core/registry";

/** Triage list: a plain list view with a styling hook. Opening a row marks
 * the conversation read through the conversation form view. */
export const triageListView = {
  ...listView,
  props: (genericProps, view) => {
    const props = listView.props(genericProps, view);
    props.className = `${props.className || ""} o_conversation_triage_list`.trim();
    return props;
  },
};

registry.category("views").add("conversation_triage_list", triageListView);
