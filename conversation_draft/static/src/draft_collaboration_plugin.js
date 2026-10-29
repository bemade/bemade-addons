// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {CollaborationOdooPlugin} from "@html_editor/others/collaboration/collaboration_odoo_plugin";
import {lastLeaf} from "@html_editor/utils/dom_traversal";

// How long a freshly joined editor waits for another editor of the same
// draft to answer before it considers itself alone.
export const NO_PEER_WINDOW = 1200;
// Upper bound of a catch-up: past it, held input is applied whatever happens.
export const MAX_CATCH_UP = 8000;
const POLL_INTERVAL = 100;

// Keys that only move the caret or leave the editor; they never change the
// document, so they are not held.
const PASS_THROUGH_KEYS = new Set([
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
  "PageUp",
  "PageDown",
  "Escape",
  "Shift",
  "Control",
  "Alt",
  "Meta",
  "CapsLock",
]);

/**
 * Collaboration for the reply draft body.
 *
 * Odoo's collaboration replaces an editor's whole document when it catches up
 * with the other editors of the same record: right after joining, the editor
 * opened last resets itself from the other's snapshot, and an editor that
 * detects a stale document resets from the peers or the server. Anything
 * typed in that window is wiped. While this editor is catching up, input is
 * held instead of applied; once the document is in sync, the held text is
 * typed into it and travels to the other editors like any other change.
 */
export class DraftCollaborationPlugin extends CollaborationOdooPlugin {
  static shared = [...CollaborationOdooPlugin.shared, "flushCatchUp", "isCatchingUp"];
  static dependencies = [...CollaborationOdooPlugin.dependencies, "dom", "split"];

  setup() {
    this.catchUpHolds = new Set();
    this.heldInput = [];
    super.setup();
    if (!this.collaborationChannelName) {
      // Not a saved record: no collaboration, nothing to catch up with.
      return;
    }
    this.addDomListener(this.editable, "keydown", this.onCatchUpKeydown, true);
    this.addDomListener(this.editable, "beforeinput", this.onCatchUpBeforeInput, true);
    this.addDomListener(this.editable, "paste", this.onCatchUpPaste, true);
    this.addDomListener(this.editable, "drop", this.onCatchUpDrop, true);
    this.startInitialCatchUp();
  }

  destroy() {
    clearInterval(this.catchUpTimer);
    super.destroy();
  }

  // ------------------------------------------------------------------
  // Catch-up state
  // ------------------------------------------------------------------

  isCatchingUp() {
    return this.catchUpHolds.size > 0;
  }

  hold(reason) {
    this.catchUpHolds.add(reason);
  }

  release(reason) {
    if (!this.catchUpHolds.delete(reason) || this.catchUpHolds.size) {
      return;
    }
    this.replayHeldInput();
  }

  /**
   * Apply held input now, whatever the catch-up state. Called before the
   * draft is saved, so that closing or sending never drops held text.
   */
  flushCatchUp() {
    clearInterval(this.catchUpTimer);
    for (const reason of [...this.catchUpHolds]) {
      this.release(reason);
    }
  }

  startInitialCatchUp() {
    // Time is counted in polling ticks rather than read from the clock.
    let elapsed = 0;
    let joinedFor = 0;
    this.hold("join");
    this.catchUpTimer = setInterval(() => {
      if (this.isDestroyed) {
        clearInterval(this.catchUpTimer);
        return;
      }
      elapsed += POLL_INTERVAL;
      if (this.ptpJoined) {
        joinedFor += POLL_INTERVAL;
      }
      const synced = this.historySyncAtLeastOnce && this.historySyncFinished;
      const knowsPeers = Boolean(this.ptp && Object.keys(this.ptp.peersInfos).length);
      const alone = !knowsPeers && joinedFor >= NO_PEER_WINDOW;
      if (synced || alone || elapsed >= MAX_CATCH_UP) {
        clearInterval(this.catchUpTimer);
        this.release("join");
      }
    }, POLL_INTERVAL);
  }

  /**
   * Replacing the document puts the caret back at the same index path, which
   * lands in the middle of the colleague's text. Someone who had the caret at
   * the end of the draft keeps writing at its end.
   */
  applySnapshot(...args) {
    const caretAtEnd = this.isCatchingUp() && this.isCaretAtDocumentEnd();
    const applied = super.applySnapshot(...args);
    if (applied && caretAtEnd) {
      this.replayAtDocumentEnd = true;
    }
    return applied;
  }

  async resetFromServerAndResyncWithPeers() {
    this.hold("server");
    try {
      return await super.resetFromServerAndResyncWithPeers();
    } finally {
      this.release("server");
    }
  }

  async recoverFromStaleDocument() {
    this.hold("stale");
    try {
      return await super.recoverFromStaleDocument();
    } finally {
      this.release("stale");
    }
  }

  // ------------------------------------------------------------------
  // Holding input
  // ------------------------------------------------------------------

  holdText(text) {
    const last = this.heldInput.at(-1);
    if (typeof last === "string") {
      this.heldInput[this.heldInput.length - 1] = last + text;
    } else {
      this.heldInput.push(text);
    }
  }

  dropLastHeldChar() {
    const last = this.heldInput.at(-1);
    if (typeof last === "string" && last.length > 1) {
      this.heldInput[this.heldInput.length - 1] = last.slice(0, -1);
    } else if (last !== undefined) {
      this.heldInput.pop();
    }
  }

  blockEvent(ev) {
    ev.preventDefault();
    ev.stopImmediatePropagation();
  }

  onCatchUpKeydown(ev) {
    if (!this.isCatchingUp() || ev.isComposing || PASS_THROUGH_KEYS.has(ev.key)) {
      return;
    }
    const modifier = ev.ctrlKey || ev.metaKey;
    if (modifier && ["c", "a"].includes(ev.key.toLowerCase())) {
      // Copy and select all change nothing.
      return;
    }
    this.blockEvent(ev);
    if (modifier) {
      return;
    }
    if (ev.key === "Enter") {
      this.heldInput.push({paragraph: true});
    } else if (ev.key === "Backspace") {
      this.dropLastHeldChar();
    } else if (ev.key.length === 1) {
      this.holdText(ev.key);
    }
  }

  onCatchUpBeforeInput(ev) {
    // Input that did not come through a held keydown (virtual keyboards,
    // dictation, autocorrect).
    if (!this.isCatchingUp()) {
      return;
    }
    this.blockEvent(ev);
    if (["insertText", "insertReplacementText"].includes(ev.inputType) && ev.data) {
      this.holdText(ev.data);
    } else if (["insertParagraph", "insertLineBreak"].includes(ev.inputType)) {
      this.heldInput.push({paragraph: true});
    }
  }

  onCatchUpPaste(ev) {
    if (!this.isCatchingUp()) {
      return;
    }
    this.blockEvent(ev);
    const text = ev.clipboardData?.getData("text/plain");
    if (text) {
      this.holdText(text);
    }
  }

  onCatchUpDrop(ev) {
    if (this.isCatchingUp()) {
      this.blockEvent(ev);
    }
  }

  isCaretAtDocumentEnd() {
    const selection = this.document.getSelection();
    if (!selection?.rangeCount || !this.editable.contains(selection.focusNode)) {
      return false;
    }
    const rest = this.document.createRange();
    rest.setStart(selection.focusNode, selection.focusOffset);
    rest.setEnd(this.editable, this.editable.childNodes.length);
    return !rest.toString().trim();
  }

  caretToDocumentEnd() {
    const leaf = lastLeaf(this.editable);
    if (leaf.nodeType === Node.TEXT_NODE) {
      this.dependencies.selection.setCursorEnd(leaf);
    } else if (leaf === this.editable) {
      this.dependencies.selection.setCursorEnd(this.editable);
    } else {
      // An empty block (<p><br></p>): write inside it.
      this.dependencies.selection.setSelection({
        anchorNode: leaf.parentElement,
        anchorOffset: 0,
      });
    }
  }

  /**
   * Type the held input into the (now synced) document at the caret, or at
   * its end when the caret was there before the reset or was lost by it.
   */
  replayHeldInput() {
    const held = this.heldInput;
    const atEnd = this.replayAtDocumentEnd;
    this.heldInput = [];
    this.replayAtDocumentEnd = false;
    if (!held.length || this.isDestroyed) {
      return;
    }
    const {selection} = this.dependencies;
    if (atEnd || !selection.getSelectionData().documentSelectionIsInEditable) {
      this.caretToDocumentEnd();
    }
    for (const item of held) {
      if (typeof item === "string") {
        this.dependencies.dom.insert(item);
      } else {
        this.dependencies.split.splitBlock();
      }
    }
    this.dependencies.history.addStep();
  }
}
