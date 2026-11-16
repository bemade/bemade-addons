/** @odoo-module **/

import { ListRenderer } from '@web/views/list/list_renderer';
import { patch } from '@web/core/utils/patch';
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { useService } from "@web/core/utils/hooks";
import { useEffect, useState } from '@odoo/owl';
import { loadChildRecords } from "./recursive_utils";

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.recursiveOrm = useService("orm");
        useState(this.props.list.records);
        // Embedded (x2many) lists have no ListController/model hook to load the
        // children: the renderer loads them for its rows after each render, so
        // added/reloaded rows get theirs too (already fetched rows are skipped).
        // Unfolded rows, by id, so they stay unfolded when the list reloads
        // (e.g. after saving the form).
        this.recursiveExpandedIds = new Set();
        useEffect(() => {
            if (this.isEmbeddedRecursive) {
                this._loadEmbeddedChildren(this.props.list.records).then(() =>
                    this._restoreExpanded(this.props.list.records)
                );
            }
        });
    },

    /**
     * `recursive="1"` makes the list recursive. On a list embedded in a form,
     * `recursive` may also be a python expression evaluated on the parent
     * record, e.g. `recursive="not parent_id"`.
     */
    get recursive() {
        const archInfo = this.props.archInfo || {};
        if (archInfo.recursiveExpr) {
            const parentRecord = this.props.list && this.props.list._parent;
            if (!parentRecord) {
                return false;
            }
            try {
                return evaluateBooleanExpr(archInfo.recursiveExpr, parentRecord.evalContext);
            } catch {
                return false;
            }
        }
        return !!archInfo.recursive;
    },

    get isEmbeddedRecursive() {
        return this.isX2Many && this.recursive;
    },

    /** Rows shown below a row of the list itself (only in embedded lists). */
    _isRecursiveChild(record) {
        return this.isEmbeddedRecursive && record.depth > 0;
    },

    async _loadEmbeddedChildren(records) {
        const list = this.props.list;
        try {
            await loadChildRecords({
                orm: this.recursiveOrm,
                model: list.model,
                config: list.config,
                records,
                maxDepth: this.props.archInfo.recursiveDepth,
                recordOptions: { parentRecord: list._parent },
            });
        } catch (error) {
            for (const record of records) {
                record.childrenFetched = true;
            }
            console.warn("recursive_list_view: could not load child rows", error);
        }
    },

    async _restoreExpanded(records) {
        for (const record of records || []) {
            if (
                record.children &&
                !record.expanded &&
                this.recursiveExpandedIds.has(record.resId)
            ) {
                await this._loadEmbeddedChildren(record.children);
                record.expanded = true;
                await this._restoreExpanded(record.children);
            }
        }
    },

    async _onExpandClick(ev, record) {
        if (record && this.isX2Many) {
            if (record.expanded) {
                record.expanded = false;
                this.recursiveExpandedIds.delete(record.resId);
            } else {
                // Prefetch the next level so children with children of their
                // own show an expand button (bounded by recursive_depth).
                await this._loadEmbeddedChildren(record.children || []);
                record.expanded = true;
                this.recursiveExpandedIds.add(record.resId);
            }
            this.render(true);
            return;
        }
        const raw = ev.currentTarget.dataset.expand;
        const parent = isNaN(raw) ? raw : Number(raw);
        this.env.bus.trigger("expand-collapse-parent", parent);
    },

    get nbCols() {
        return super.nbCols + (this.recursive ? 1 : 0);
    },

    getGroupNameCellColSpan(group) {
        return super.getGroupNameCellColSpan(...arguments) + (this.recursive ? 1 : 0);
    },

    // Child rows of an embedded list are not part of the x2many value: they are
    // shown read-only, cannot be dragged or deleted, and a click opens them.
    getRowClass(record) {
        const classNames = super.getRowClass(record);
        if (!this._isRecursiveChild(record)) {
            return classNames;
        }
        return classNames
            .split(" ")
            .filter((className) => className && className !== "o_row_draggable")
            .concat(["o_recursive_child_row"])
            .join(" ");
    },

    isRecordReadonly(record) {
        return this._isRecursiveChild(record) || super.isRecordReadonly(record);
    },

    isInlineEditable(record) {
        return !this._isRecursiveChild(record) && super.isInlineEditable(record);
    },

    displayDeleteIcon(record) {
        return !this._isRecursiveChild(record) && super.displayDeleteIcon(record);
    },

    async onDeleteRecord(record) {
        if (this._isRecursiveChild(record)) {
            return;
        }
        return super.onDeleteRecord(...arguments);
    },

    async onCellClicked(record, column, ev, newWindow) {
        if (this._isRecursiveChild(record)) {
            if (ev.target.special_click) {
                return;
            }
            if (this.props.onOpenFormView) {
                return this.props.onOpenFormView(record, { newWindow });
            }
            return;
        }
        return super.onCellClicked(...arguments);
    },
});
