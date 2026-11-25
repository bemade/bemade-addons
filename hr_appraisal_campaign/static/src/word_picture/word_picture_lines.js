import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * One card per criterion, grouped by section; the word pictures of every level of
 * the campaign's scale are shown side by side (stacked on a phone) and clicking one
 * IS the grade. The employee's choice and the manager's / final choice are marked on
 * the cards so both descriptions can be compared. Which grade a click sets, and what
 * is visible, is decided by the server (can_edit_* / can_see_* flags on each line).
 * The levels come from the line (levels_data: value, name, text, colour).
 */
export class WordPictureLines extends Component {
    static template = "hr_appraisal_campaign.WordPictureLines";
    static props = { ...standardFieldProps };

    get records() {
        return this.props.record.data[this.props.name].records;
    }

    get sections() {
        const sections = [];
        const byKey = {};
        for (const rec of this.records) {
            const section = rec.data.section_id;
            const key = section ? section.id : 0;
            if (!(key in byKey)) {
                byKey[key] = { key, name: section ? section.display_name : "", records: [] };
                sections.push(byKey[key]);
            }
            byKey[key].records.push(rec);
        }
        sections.forEach((section, index) => {
            section.label = section.name ? `${index + 1}. ${section.name}` : "";
        });
        return sections;
    }

    get progress() {
        const editable = this.records.filter((rec) => this.gradeField(rec));
        if (!editable.length) {
            return null;
        }
        const graded = editable.filter((rec) => rec.data[this.gradeField(rec)]).length;
        return _t("%(graded)s of %(total)s criteria graded", {
            graded,
            total: editable.length,
        });
    }

    levels(rec) {
        return rec.data.levels_data || [];
    }

    /** Bootstrap grid column for a level card: up to 4 per row on a wide screen,
     * 5 or 6 levels share one row on an extra-wide one. */
    columnClass(rec) {
        const count = this.levels(rec).length;
        if (count <= 2) {
            return "col-12 col-md-6";
        }
        if (count === 3) {
            return "col-12 col-md-4";
        }
        if (count === 4) {
            return "col-12 col-md-6 col-xl-3";
        }
        return "col-12 col-md-6 col-xl";
    }

    /** The grade field a click on this card sets, or null when read-only. */
    gradeField(rec) {
        if (this.props.readonly) {
            return null;
        }
        if (rec.data.can_edit_employee) {
            return "employee_grade_ui";
        }
        if (rec.data.can_edit_manager) {
            return "manager_grade_ui";
        }
        return null;
    }

    /** Remarks stay editable by the evaluator after the grades are locked, until the
     * employee acknowledges the evaluation (server flag can_edit_remarks). */
    canEditRemarks(rec) {
        return !this.props.readonly && Boolean(rec.data.can_edit_remarks);
    }

    managerGrade(rec) {
        return rec.data.can_edit_manager
            ? rec.data.manager_grade_ui
            : rec.data.final_grade_ui || rec.data.manager_grade_ui;
    }

    managerMark(rec) {
        return rec.data.can_edit_manager ? _t("Manager") : _t("Final");
    }

    /** The grade the card highlights: the one being edited, else the most recent. */
    mainGrade(rec) {
        const field = this.gradeField(rec);
        if (field) {
            return rec.data[field];
        }
        if (rec.data.can_see_manager && this.managerGrade(rec)) {
            return this.managerGrade(rec);
        }
        return rec.data.can_see_employee ? rec.data.employee_grade_ui : 0;
    }

    levelClass(rec, level) {
        const classes = [
            "o_campaign_wp_level",
            "h-100",
            "p-2",
            "rounded",
            "border",
            `o_campaign_wp_level_${level.value}`,
            `o_campaign_wp_color_${level.color || "secondary"}`,
        ];
        if (this.mainGrade(rec) === level.value) {
            classes.push("o_campaign_wp_selected");
        }
        if (this.gradeField(rec)) {
            classes.push("o_campaign_wp_editable");
        }
        return classes.join(" ");
    }

    badgeClass(level) {
        return `text-bg-${level.color || "secondary"}`;
    }

    async select(rec, value) {
        const field = this.gradeField(rec);
        if (!field) {
            return;
        }
        await rec.update({ [field]: value });
    }

    onKeydown(ev, rec, value) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.select(rec, value);
        }
    }

    async onCommentChange(rec, field, ev) {
        await rec.update({ [field]: ev.target.value });
    }
}

export const campaignWordPictureLines = {
    component: WordPictureLines,
    displayName: _t("Word-picture grades"),
    supportedTypes: ["one2many"],
    // related fields default to read-only (never saved): the editable ones say so
    relatedFields: [
        { name: "name", type: "char" },
        { name: "description", type: "text" },
        { name: "section_id", type: "many2one", relation: "hr.appraisal.campaign.section" },
        { name: "sequence", type: "integer" },
        { name: "levels_data", type: "json" },
        { name: "employee_grade_ui", type: "integer", readonly: false },
        { name: "employee_examples_ui", type: "text", readonly: false },
        { name: "manager_grade_ui", type: "integer", readonly: false },
        { name: "manager_remarks_ui", type: "text", readonly: false },
        { name: "final_grade_ui", type: "integer", readonly: true },
        { name: "can_edit_employee", type: "boolean", readonly: true },
        { name: "can_edit_manager", type: "boolean", readonly: true },
        { name: "can_edit_remarks", type: "boolean", readonly: true },
        { name: "can_see_employee", type: "boolean", readonly: true },
        { name: "can_see_manager", type: "boolean", readonly: true },
    ],
};

registry.category("fields").add("campaign_word_picture_lines", campaignWordPictureLines);
