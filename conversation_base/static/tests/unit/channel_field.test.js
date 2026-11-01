// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
//
// The channel icon of the triage list loads the provider labels once per
// page and shares them between every row. A list render that is replaced
// before it finishes (a search typed while the list is still loading)
// throws away the rows that asked for the labels first. The rows of the
// new render must still get the labels and show, instead of waiting
// forever and holding the whole list back.
import {Component, useState, xml} from "@odoo/owl";
import {
  ConversationChannelField,
  resetProviderLabels,
} from "@conversation_base/triage/triage_fields";
import {Deferred, animationFrame} from "@odoo/hoot-mock";
import {expect, test} from "@odoo/hoot";
import {mountWithCleanup, onRpc} from "@web/../tests/web_test_helpers";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";

// The mail services start with any backend page: give them their models.
defineMailModels();

class Rows extends Component {
  static template = xml`
    <div class="o_rows">
      <t t-if="state.show">
        <ConversationChannelField t-key="state.generation" record="record" name="'triage_channel'"/>
      </t>
    </div>`;
  static components = {ConversationChannelField};
  static props = ["*"];

  setup() {
    this.state = useState({show: false, generation: 1});
    this.record = {data: {triage_channel: "imap"}};
  }
}

test("a replaced list render still shows the channel icon", async () => {
  resetProviderLabels();
  const labels = new Deferred();
  let calls = 0;
  onRpc("conversation.transport", "fields_get", () => {
    calls++;
    return labels;
  });
  const rows = await mountWithCleanup(Rows);

  // The list starts rendering a row: its icon asks for the labels.
  rows.state.show = true;
  await animationFrame();
  expect(calls).toBe(1);
  expect(".o_conversation_channel").toHaveCount(0);

  // A new render replaces that row before the labels arrive.
  rows.state.generation = 2;
  await animationFrame();
  labels.resolve({provider: {selection: [["imap", "Email (IMAP)"]]}});
  await animationFrame();
  await animationFrame();

  expect(".o_conversation_channel").toHaveCount(1);
  expect(".o_conversation_channel").toHaveAttribute("title", "Email (IMAP)");
  expect(calls).toBe(1);
});

test("the labels are fetched once for every row", async () => {
  resetProviderLabels();
  let calls = 0;
  onRpc("conversation.transport", "fields_get", () => {
    calls++;
    return {provider: {selection: [["gmail", "Gmail"]]}};
  });
  const rows = await mountWithCleanup(Rows);
  rows.record.data.triage_channel = "gmail";
  rows.state.show = true;
  await animationFrame();
  rows.state.generation = 2;
  await animationFrame();
  expect(".o_conversation_channel").toHaveAttribute("title", "Gmail");
  expect(calls).toBe(1);
});
