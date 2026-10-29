// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
//
// Two people edit the same reply draft at once. The peer network is
// simulated in the page (same approach as html_editor's own collaboration
// tests): each editor is a real html_editor instance with the draft's
// collaboration plugin, and opening a "data channel" between two editors is
// what a WebRTC connection does in the browser.
import {CollaborationOdooPlugin} from "@html_editor/others/collaboration/collaboration_odoo_plugin";
import {COLLABORATION_PLUGINS, MAIN_PLUGINS} from "@html_editor/plugin_sets";
import {Wysiwyg} from "@html_editor/wysiwyg";
import {beforeEach, describe, expect, test} from "@odoo/hoot";
import {advanceTime, animationFrame} from "@odoo/hoot-dom";
import {Component, markup, xml} from "@odoo/owl";
import {mountWithCleanup, onRpc} from "@web/../tests/web_test_helpers";
import {patch} from "@web/core/utils/patch";
import {getSelection, setSelection} from "@html_editor/../tests/_helpers/selection";
import {insertText} from "@html_editor/../tests/_helpers/user_actions";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {
  DraftCollaborationPlugin,
  NO_PEER_WINDOW,
} from "@conversation_draft/draft_collaboration_plugin";

const DRAFT_COLLABORATION_PLUGINS = COLLABORATION_PLUGINS.map((Plugin) =>
  Plugin === CollaborationOdooPlugin ? DraftCollaborationPlugin : Plugin
);

class Peer {
  constructor(peerId, pool) {
    this.peerId = peerId;
    this.pool = pool;
    this.connections = new Set();
  }
  get plugin() {
    return this.plugins.collaborationOdoo;
  }
  text() {
    return this.editor.editable.textContent;
  }
  /** What a WebRTC data channel opening between two editors does. */
  async openDataChannel(other) {
    this.connections.add(other);
    other.connections.add(this);
    this.ptp.peersInfos[other.peerId] ||= {};
    other.ptp.peersInfos[this.peerId] ||= {};
    await this.ptp.notifySelf("rtc_data_channel_open", {
      connectionPeerId: other.peerId,
    });
    await other.ptp.notifySelf("rtc_data_channel_open", {
      connectionPeerId: this.peerId,
    });
  }
  /** Real key events on the editor, as a user types. */
  async typeKeys(text) {
    for (const key of text) {
      const ev = new KeyboardEvent("keydown", {key, bubbles: true, cancelable: true});
      this.editor.editable.dispatchEvent(ev);
      if (!ev.defaultPrevented) {
        // Not held: the browser would type it, so type it the editor's way.
        await insertText(this.editor, key);
        this.editor.shared.history.addStep();
      }
    }
  }
}

class Editors extends Component {
  static template = xml`
    <div>
      <t t-foreach="props.peerIds" t-as="peerId" t-key="peerId">
        <Wysiwyg config="getConfig(peerId)" iframe="true" onLoad="(editor) => this.onLoad(peerId, editor)"/>
      </t>
    </div>`;
  static components = {Wysiwyg};
  static props = ["peerIds", "pool", "content"];

  setup() {
    this.lastStepId = 0;
  }

  getConfig(peerId) {
    const noop = () => undefined;
    const busService = {
      subscribe: noop,
      unsubscribe: noop,
      addEventListener: noop,
      removeEventListener: noop,
      addChannel: noop,
      deleteChannel: noop,
    };
    return {
      Plugins: [...MAIN_PLUGINS, ...DRAFT_COLLABORATION_PLUGINS],
      content: markup(this.props.content.replace("[]", "")),
      collaboration: {
        peerId,
        busService,
        collaborationChannel: {
          collaborationFieldName: "body",
          collaborationModelName: "mail.conversation.draft",
          collaborationResId: 1,
        },
        // As on the draft views.
        collaborativeTrigger: "start",
      },
    };
  }

  onLoad(peerId, editor) {
    const {pool} = this.props;
    const peer = pool.peers[peerId];
    const startPlugins = editor.startPlugins.bind(editor);
    const attachTo = editor.attachTo.bind(editor);
    const component = this;
    editor.startPlugins = () => {
      const plugins = Object.fromEntries(
        editor.plugins.map((p) => [p.constructor.id, p])
      );
      Object.assign(peer, {editor, plugins});
      patch(plugins.collaborationOdoo, {
        getNewPtp() {
          // The editor opened first is the one the others catch up with.
          this.startCollaborationTime = parseInt(peerId.match(/\d+/)[0], 10);
          const ptp = super.getNewPtp();
          peer.ptp = ptp;
          patch(ptp, {
            notifyAllPeers(name, ...args) {
              if (name === "ptp_join") {
                return;
              }
              this.options.broadcastAll = (params) => {
                for (const other of peer.connections) {
                  other.ptp.handleNotification(structuredClone(params));
                }
              };
              return super.notifyAllPeers(name, ...args);
            },
            async _channelNotify(toPeerId, payload) {
              pool.peers[toPeerId].ptp.handleNotification(structuredClone(payload));
            },
            _createPeer() {
              throw new Error("No real WebRTC in this test.");
            },
          });
          pool.resolvers[peerId]();
          return ptp;
        },
        getCurrentRecord() {
          return {id: 1, body: pool.serverBody};
        },
      });
      patch(plugins.history, {
        generateId: () => `${++component.lastStepId}`,
      });
      return startPlugins();
    };
    editor.attachTo = (el) => {
      const editable = document.createElement("div");
      el.replaceChildren(editable);
      attachTo(editable);
      setSelection(getSelection(editable, this.props.content));
    };
  }
}

async function openEditors(
  peerIds,
  content = `<p data-last-history-steps="1">a[]</p>`
) {
  const pool = {peers: {}, resolvers: {}, serverBody: content.replace("[]", "")};
  const ready = [];
  for (const peerId of peerIds) {
    pool.peers[peerId] = new Peer(peerId, pool);
    ready.push(new Promise((resolve) => (pool.resolvers[peerId] = resolve)));
  }
  await mountWithCleanup(Editors, {props: {peerIds, pool, content}});
  await Promise.all(ready);
  await animationFrame();
  return pool.peers;
}

defineMailModels();

beforeEach(() => {
  onRpc("res.users", "read", () => [{id: 0, name: "admin"}]);
  onRpc("/html_editor/get_ice_servers", () => []);
  onRpc("/html_editor/bus_broadcast", () => {
    throw new Error("Steps travel over the data channel only.");
  });
});

describe("two people on one reply draft", () => {
  test("an idle editor receives a colleague's typing", async () => {
    const {p1, p2} = await openEditors(["p1", "p2"]);
    // Nobody clicked into either editor: both joined when they opened.
    expect(p1.plugin.ptpJoined).toBe(true);
    expect(p2.plugin.ptpJoined).toBe(true);
    await p1.openDataChannel(p2);
    await advanceTime(200);

    await insertText(p1.editor, "b");
    p1.editor.shared.history.addStep();
    await animationFrame();

    expect(p2.text()).toBe("ab");
  });

  test("typing while the editor catches up is kept", async () => {
    const {p1, p2} = await openEditors(["p1", "p2"]);
    // P1 is the colleague already working on the draft. p2 opened it later:
    // p1's WebRTC offer has reached p2, the data channel is not open yet.
    p2.ptp.peersInfos[p1.peerId] = {};
    await advanceTime(NO_PEER_WINDOW + 200);
    expect(p1.plugin.isCatchingUp()).toBe(false);
    await insertText(p1.editor, "b");
    p1.editor.shared.history.addStep();

    // P2 opened the draft and types before its editor caught up with p1.
    expect(p2.plugin.isCatchingUp()).toBe(true);
    await p2.typeKeys("c");
    expect(p2.text()).toBe("a", {message: "held, not applied to a stale document"});

    // The data channel opens: p2 resets from p1's document, then types
    // what was held into it.
    await p1.openDataChannel(p2);
    await advanceTime(200);
    await animationFrame();

    expect(p2.plugin.isCatchingUp()).toBe(false);
    // P2's caret was at the end of the draft: what it typed goes at the end.
    expect(p2.text()).toBe("abc");
    expect(p1.text()).toBe("abc", {message: "the held text reached the colleague"});

    // From then on both type freely and keep each other's text.
    await p2.typeKeys("d");
    await insertText(p1.editor, "e");
    p1.editor.shared.history.addStep();
    await animationFrame();
    for (const peer of [p1, p2]) {
      for (const letter of "bcde") {
        expect(peer.text()).toInclude(letter);
      }
    }
    expect(p1.text()).toBe(p2.text());
  });

  test("an editor alone applies what was typed once nobody answers", async () => {
    const {p1} = await openEditors(["p1"]);
    expect(p1.plugin.isCatchingUp()).toBe(true);
    await p1.typeKeys("xy");
    expect(p1.text()).toBe("a");
    await advanceTime(NO_PEER_WINDOW + 200);
    await animationFrame();
    expect(p1.plugin.isCatchingUp()).toBe(false);
    expect(p1.text()).toBe("axy");
  });

  test("saving applies held text first", async () => {
    const {p1} = await openEditors(["p1"]);
    await p1.typeKeys("z");
    expect(p1.text()).toBe("a");
    p1.editor.shared.collaborationOdoo.flushCatchUp();
    expect(p1.plugin.isCatchingUp()).toBe(false);
    expect(p1.editor.getContent()).toInclude("az");
  });
});
