// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
import {HistoryPlugin} from "@html_editor/core/history_plugin";

/**
 * The edit that turns `from` into `to`: the longest common prefix, then the
 * longest common suffix of what remains. Canonical, so every editor computes
 * the same edit from the same pair of texts.
 *
 * @param {string} from
 * @param {string} to
 * @returns {{pos: number, del: number, ins: string}} replace `del` characters
 *          at `pos` with `ins`
 */
export function textEdit(from, to) {
  const max = Math.min(from.length, to.length);
  let pos = 0;
  while (pos < max && from[pos] === to[pos]) {
    pos++;
  }
  let suffix = 0;
  while (
    suffix < max - pos &&
    from[from.length - 1 - suffix] === to[to.length - 1 - suffix]
  ) {
    suffix++;
  }
  return {pos, del: from.length - pos - suffix, ins: to.slice(pos, to.length - suffix)};
}

/**
 * Transplant the edit (`from` → `to`) onto `current`, a text that already
 * received another change since `from`. The edit stays where it was when it
 * lies before that change, shifts when it lies after it, and when both
 * inserted at the very same position, `continuesRun(pos)` decides whether the
 * new text goes before the other change (it continues its author's run) or
 * after it. When the two changes overlap, what is there stays and the new
 * text goes after it: text is never lost.
 *
 * @param {string} from
 * @param {string} to
 * @param {string} current
 * @param {(pos: number) => boolean} continuesRun
 * @returns {{pos: number, del: number, ins: string}} the edit, in `current` coordinates
 */
export function transplantEdit(from, to, current, continuesRun) {
  const edit = textEdit(from, to);
  const change = textEdit(from, current);
  const editEnd = edit.pos + edit.del;
  const changeEnd = change.pos + change.del;
  if (
    editEnd < change.pos ||
    (editEnd === change.pos && (edit.del > 0 || continuesRun(edit.pos)))
  ) {
    return edit;
  }
  if (edit.pos >= changeEnd) {
    return {...edit, pos: edit.pos + current.length - from.length};
  }
  return {pos: change.pos + change.ins.length, del: 0, ins: edit.ins};
}

function applyEdit(text, {pos, del, ins}) {
  return text.slice(0, pos) + ins + text.slice(pos + del);
}

/**
 * The edit recorded on a mutation by its last application, forward
 * (`appliedOldValue` → `appliedValue`) or inverted.
 */
function recordedEdit(mutation, inverted) {
  const {appliedOldValue, appliedValue, appliedPos: pos, appliedDel: del} = mutation;
  const insLength = appliedValue.length - appliedOldValue.length + del;
  if (inverted) {
    return {pos, del: insLength, ins: appliedOldValue.slice(pos, pos + del)};
  }
  return {pos, del, ins: appliedValue.slice(pos, pos + insLength)};
}

function nodeSize(node) {
  return node.nodeType === Node.TEXT_NODE ? node.length : node.childNodes.length;
}

/**
 * History for the reply draft body: concurrent typing merges instead of
 * overwriting.
 *
 * Odoo records a keystroke as a `characterData` mutation holding the whole
 * text node before and after, and applies it with `textContent = value`. When
 * two people type in the same paragraph at the same moment, their steps are
 * concurrent and the one applied last replaces the node, so the other
 * person's letters vanish on both sides. This plugin applies such a mutation
 * as an edit (position, deleted count, inserted text) and, when the node has
 * changed since the mutation was recorded, transplants the edit onto the
 * current text. Each application records what it actually did on the
 * mutation (`applied*`), so reverting and re-applying stay exact. Both
 * editors apply the same ordered steps with the same deterministic rules, so
 * they converge on the same text.
 *
 * It also tracks the caret through the text edits applied while external
 * steps are integrated (see `withRemappedSelection`), so a colleague's insert
 * before the caret never leaves it one character back.
 */
export class DraftHistoryPlugin extends HistoryPlugin {
  static shared = [...HistoryPlugin.shared, "withRemappedSelection"];

  /** @type {WeakMap<Object, Object>} mutation → the step it belongs to */
  mutationSteps = new WeakMap();
  /** @type {WeakMap<Node, Array<string|null>>} text node → author of each character */
  authorTags = new WeakMap();
  /** @type {Array<{node: Node, offset: number}>|null} */
  trackedPoints = null;
  stepBeingReverted = null;

  get localPeerId() {
    return this.config.collaboration?.peerId;
  }

  // ------------------------------------------------------------------
  // Knowing which step a mutation belongs to
  // ------------------------------------------------------------------

  rememberSteps(steps) {
    for (const step of steps) {
      for (const mutation of step.mutations) {
        this.mutationSteps.set(mutation, step);
      }
    }
  }

  addStep(params) {
    const step = super.addStep(params);
    if (step) {
      this.rememberSteps([step]);
      for (const mutation of step.mutations) {
        if (mutation.type === "characterData") {
          this.recordTypedText(mutation, step);
        }
      }
    }
    return step;
  }

  addExternalStep(newStep, index) {
    this.rememberSteps([newStep, ...this.steps.slice(index), this.currentStep]);
    super.addExternalStep(newStep, index);
  }

  resetFromSteps(steps) {
    this.rememberSteps(steps);
    super.resetFromSteps(steps);
  }

  revertMutations(mutations, options) {
    const previous = this.stepBeingReverted;
    this.stepBeingReverted = this.stepOf(mutations[0]);
    try {
      super.revertMutations(mutations, options);
    } finally {
      this.stepBeingReverted = previous;
    }
  }

  stepOf(mutation) {
    return (mutation && this.mutationSteps.get(mutation)) || this.currentStep;
  }

  // ------------------------------------------------------------------
  // Applying text mutations as edits
  // ------------------------------------------------------------------

  applyMutations(mutations, options = {}) {
    let run = [];
    const flush = () => {
      if (run.length) {
        super.applyMutations(run, options);
        run = [];
      }
    };
    for (const mutation of mutations) {
      if (mutation.type === "characterData") {
        flush();
        this.applyTextMutation(mutation, options);
      } else {
        run.push(mutation);
      }
    }
    flush();
  }

  /**
   * A keystroke of this editor: the DOM already changed, record the edit it
   * made so later reverts and re-applies are exact, and tag its author.
   */
  recordTypedText(mutation, step) {
    const node = this.nodeMap.getNode(mutation.nodeId);
    if (!node) {
      return;
    }
    const edit = textEdit(mutation.oldValue, mutation.value);
    Object.assign(mutation, {
      appliedOldValue: mutation.oldValue,
      appliedValue: mutation.value,
      appliedPos: edit.pos,
      appliedDel: edit.del,
    });
    const tags = this.tagsFor(node, mutation.oldValue);
    this.authorTags.set(node, this.tagsAfter(tags, edit, step.peerId));
  }

  applyTextMutation(mutation, {reverse} = {}) {
    const node = this.nodeMap.getNode(mutation.nodeId);
    if (!node) {
      return;
    }
    const current = node.textContent;
    const step = reverse ? this.stepBeingReverted : this.stepOf(mutation);
    const author = step?.peerId;
    const tags = this.tagsFor(node, current);
    const continuesRun = (pos) => pos > 0 && tags[pos - 1] === author;
    const edit = reverse
      ? this.revertingEdit(mutation, current, continuesRun)
      : this.forwardEdit(mutation, current, continuesRun);
    const result = applyEdit(current, edit);
    if (!reverse) {
      Object.assign(mutation, {
        appliedOldValue: current,
        appliedValue: result,
        appliedPos: edit.pos,
        appliedDel: edit.del,
      });
    }
    this.remapTrackedPoints(node, edit, author, tags);
    this.authorTags.set(node, this.tagsAfter(tags, edit, author));
    if (result !== current) {
      node.textContent = result;
    }
  }

  /**
   * The edit a mutation makes to `current`: its own when the node still
   * reads as recorded, the one of its last application when the node is back
   * in that state, else its edit transplanted onto the current text.
   */
  forwardEdit(mutation, current, continuesRun) {
    if (current === mutation.oldValue) {
      return textEdit(mutation.oldValue, mutation.value);
    }
    if (mutation.appliedPos !== undefined && current === mutation.appliedOldValue) {
      return recordedEdit(mutation, false);
    }
    return transplantEdit(mutation.oldValue, mutation.value, current, continuesRun);
  }

  /**
   * Same, for the reverted copy Odoo hands over: `value` and `oldValue` are
   * swapped and the `applied*` fields of the last forward application come
   * along, so undo what that application actually did.
   */
  revertingEdit(mutation, current, continuesRun) {
    const from = mutation.appliedValue ?? mutation.oldValue;
    const to = mutation.appliedOldValue ?? mutation.value;
    if (current !== from) {
      return transplantEdit(from, to, current, continuesRun);
    }
    return mutation.appliedPos === undefined
      ? textEdit(from, to)
      : recordedEdit(mutation, true);
  }

  // ------------------------------------------------------------------
  // Who typed what
  // ------------------------------------------------------------------

  tagsFor(node, text) {
    const tags = this.authorTags.get(node);
    return tags && tags.length === text.length
      ? tags
      : new Array(text.length).fill(null);
  }

  tagsAfter(tags, {pos, del, ins}, author) {
    return tags
      .slice(0, pos)
      .concat(new Array(ins.length).fill(author), tags.slice(pos + del));
  }

  // ------------------------------------------------------------------
  // Keeping the caret with the user's own text
  // ------------------------------------------------------------------

  /**
   * Run `fn` (the integration of external steps) and move the selection to
   * where the tracked points ended up, after Odoo restored the old offsets.
   */
  withRemappedSelection(fn) {
    const {documentSelectionIsInEditable, editableSelection} =
      this.dependencies.selection.getSelectionData();
    if (!documentSelectionIsInEditable || this.trackedPoints) {
      return fn();
    }
    const {anchorNode, anchorOffset, focusNode, focusOffset} = editableSelection;
    const points = [
      {node: anchorNode, offset: anchorOffset},
      {node: focusNode, offset: focusOffset},
    ];
    this.trackedPoints = points;
    try {
      return fn();
    } finally {
      this.trackedPoints = null;
      const [anchor, focus] = points;
      const usable = (point) =>
        point.node.isConnected &&
        this.editable.contains(point.node) &&
        point.offset <= nodeSize(point.node);
      if (
        (anchor.offset !== anchorOffset || focus.offset !== focusOffset) &&
        usable(anchor) &&
        usable(focus)
      ) {
        this.dependencies.selection.setSelection(
          {
            anchorNode: anchor.node,
            anchorOffset: anchor.offset,
            focusNode: focus.node,
            focusOffset: focus.offset,
          },
          {normalize: false}
        );
      }
    }
  }

  /**
   * Move the tracked points through one text edit. An edit before a point
   * shifts it, one after it leaves it. An insert exactly at the point pushes
   * it past the new text, except a colleague's insert right after this
   * user's own letters: the user keeps writing at the end of their run.
   */
  remapTrackedPoints(node, {pos, del, ins}, author, tagsBefore) {
    if (!this.trackedPoints) {
      return;
    }
    for (const point of this.trackedPoints) {
      if (point.node !== node) {
        continue;
      }
      if (point.offset > pos + del) {
        point.offset += ins.length - del;
      } else if (point.offset > pos) {
        point.offset = pos + ins.length;
      } else if (point.offset === pos && del === 0 && ins.length) {
        const own = author === this.localPeerId;
        const afterMine = pos > 0 && tagsBefore[pos - 1] === this.localPeerId;
        if (own || !afterMine) {
          point.offset += ins.length;
        }
      }
    }
  }
}
