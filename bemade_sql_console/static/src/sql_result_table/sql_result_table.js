/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, useState } from "@odoo/owl";

const PAGE_SIZES = [25, 50, 100];

/**
 * Read-only field widget that renders a SQL console result envelope
 * ({columns, rows, row_count, truncated}) as an HTML table with client-side
 * pagination.
 *
 * Grounded against web/static/src/views/fields/boolean/boolean_field.js and
 * json/json_field.js (Odoo 19.0) for the Component + standardFieldProps +
 * registry.category("fields").add(...) pattern.
 */
export class SqlResultTable extends Component {
    static template = "bemade_sql_console.SqlResultTable";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            page: 0,
            pageSize: PAGE_SIZES[0],
        });
        this.pageSizes = PAGE_SIZES;
    }

    /** The raw envelope, or a safe empty default. */
    get envelope() {
        const value = this.props.record.data[this.props.name];
        if (!value || typeof value !== "object") {
            return { columns: [], rows: [], row_count: 0, truncated: false };
        }
        return {
            columns: Array.isArray(value.columns) ? value.columns : [],
            rows: Array.isArray(value.rows) ? value.rows : [],
            row_count: value.row_count || 0,
            truncated: Boolean(value.truncated),
        };
    }

    get columns() {
        return this.envelope.columns;
    }

    get allRows() {
        return this.envelope.rows;
    }

    get truncated() {
        return this.envelope.truncated;
    }

    get hasResult() {
        return this.columns.length > 0 || this.allRows.length > 0;
    }

    get totalRows() {
        return this.allRows.length;
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.totalRows / this.state.pageSize));
    }

    /** Clamp the page index into [0, pageCount - 1]. */
    get currentPage() {
        const max = this.pageCount - 1;
        if (this.state.page > max) {
            return max;
        }
        return this.state.page < 0 ? 0 : this.state.page;
    }

    get pageRows() {
        const start = this.currentPage * this.state.pageSize;
        return this.allRows.slice(start, start + this.state.pageSize);
    }

    /** 1-based index of the first row shown (0 when empty). */
    get firstRowIndex() {
        return this.totalRows === 0 ? 0 : this.currentPage * this.state.pageSize + 1;
    }

    /** 1-based index of the last row shown. */
    get lastRowIndex() {
        return Math.min((this.currentPage + 1) * this.state.pageSize, this.totalRows);
    }

    get rangeLabel() {
        return _t("Row %(from)s–%(to)s of %(total)s", {
            from: this.firstRowIndex,
            to: this.lastRowIndex,
            total: this.totalRows,
        });
    }

    /** Render a single cell value for display. */
    formatCell(value) {
        if (value === null || value === undefined) {
            return "";
        }
        if (typeof value === "object") {
            return JSON.stringify(value);
        }
        return String(value);
    }

    onPrev() {
        if (this.currentPage > 0) {
            this.state.page = this.currentPage - 1;
        }
    }

    onNext() {
        if (this.currentPage < this.pageCount - 1) {
            this.state.page = this.currentPage + 1;
        }
    }

    onPageSizeChange(ev) {
        this.state.pageSize = parseInt(ev.target.value, 10) || PAGE_SIZES[0];
        this.state.page = 0;
    }
}

export const sqlResultTable = {
    component: SqlResultTable,
    displayName: _t("SQL Result Table"),
    supportedTypes: ["json"],
};

registry.category("fields").add("sql_result_table", sqlResultTable);
