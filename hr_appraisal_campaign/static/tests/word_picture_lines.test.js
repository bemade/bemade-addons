import { expect, test } from "@odoo/hoot";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
} from "@web/../tests/web_test_helpers";

class Appraisal extends models.Model {
    _name = "hr.appraisal";
    campaign_line_ids = fields.One2many({ relation: "hr.appraisal.campaign.line" });
    _records = [{ id: 1, campaign_line_ids: [1, 2, 3] }];
}

class Section extends models.Model {
    _name = "hr.appraisal.campaign.section";
    name = fields.Char();
    _records = [
        { id: 1, name: "Values" },
        { id: 2, name: "Job" },
    ];
}

const COLORS = ["danger", "warning", "secondary", "info", "success"];
const NAMES = ["Very low", "Low", "Medium", "High", "Very high"];
// a 5-level scale: the widget draws as many cards as the scale has levels
const LEVELS = NAMES.map((name, i) => ({
    value: i + 1,
    name,
    text: `${name}: picture ${i + 1}`,
    color: COLORS[i],
}));

class Line extends models.Model {
    _name = "hr.appraisal.campaign.line";
    name = fields.Char();
    description = fields.Text();
    section_id = fields.Many2one({ relation: "hr.appraisal.campaign.section" });
    sequence = fields.Integer();
    levels_data = fields.Json();
    employee_grade_ui = fields.Integer();
    employee_examples_ui = fields.Text();
    manager_grade_ui = fields.Integer();
    manager_remarks_ui = fields.Text();
    final_grade_ui = fields.Integer();
    can_edit_employee = fields.Boolean();
    can_edit_manager = fields.Boolean();
    can_edit_remarks = fields.Boolean();
    can_see_employee = fields.Boolean();
    can_see_manager = fields.Boolean();
    _records = [
        {
            id: 1, name: "Teamwork", section_id: 1, levels_data: LEVELS,
            can_edit_employee: true, can_see_employee: true,
        },
        {
            id: 2, name: "Quality", section_id: 2, levels_data: LEVELS,
            employee_grade_ui: 2, manager_grade_ui: 5, final_grade_ui: 5,
            can_see_employee: true, can_see_manager: true,
        },
        {
            // calibration / meeting step: grades locked, remarks still editable
            id: 3, name: "Rigour", section_id: 2, levels_data: LEVELS,
            employee_grade_ui: 3, manager_grade_ui: 2, final_grade_ui: 2,
            manager_remarks_ui: "Draft remark",
            can_see_employee: true, can_see_manager: true, can_edit_remarks: true,
        },
    ];
}

defineMailModels();
defineModels([Appraisal, Section, Line]);

const ARCH = `<form><field name="campaign_line_ids" widget="campaign_word_picture_lines"/></form>`;

test("campaign_word_picture: one card per level, a click sets the grade", async () => {
    onRpc("web_save", ({ args }) => {
        expect.step(JSON.stringify(args[1].campaign_line_ids));
    });
    await mountView({ type: "form", resModel: "hr.appraisal", resId: 1, arch: ARCH });
    expect(".o_campaign_wp_criterion").toHaveCount(3);
    expect(".o_campaign_wp_section").toHaveCount(2);
    expect(".o_campaign_wp_section:eq(0)").toHaveText("1. Values");
    expect(".o_campaign_wp_section:eq(1)").toHaveText("2. Job");
    expect(".o_campaign_wp_criterion:eq(0) .o_campaign_wp_level").toHaveCount(5);
    expect(".o_campaign_wp_criterion:eq(0) .o_campaign_wp_level_5").toHaveText(/Very high: picture 5/);
    expect(".o_campaign_wp_criterion:eq(0) .o_campaign_wp_level_1 .badge").toHaveClass("text-bg-danger");
    await contains(".o_campaign_wp_criterion:eq(0) .o_campaign_wp_level[data-level='4']").click();
    expect(".o_campaign_wp_criterion:eq(0) .o_campaign_wp_level_4").toHaveClass("o_campaign_wp_selected");
    await contains(".o_form_button_save").click();
    expect.verifySteps([JSON.stringify([[1, 1, { employee_grade_ui: 4 }]])]);
});

test("campaign_word_picture: read-only criterion shows both choices and ignores clicks", async () => {
    await mountView({ type: "form", resModel: "hr.appraisal", resId: 1, arch: ARCH });
    const card = ".o_campaign_wp_criterion:eq(1)";
    expect(`${card} .o_campaign_wp_level_2 .o_campaign_wp_mark_self`).toHaveCount(1);
    expect(`${card} .o_campaign_wp_level_5 .o_campaign_wp_mark_manager`).toHaveCount(1);
    expect(`${card} .o_campaign_wp_level_5`).toHaveClass("o_campaign_wp_selected");
    await contains(`${card} .o_campaign_wp_level[data-level='1']`).click();
    expect(`${card} .o_campaign_wp_level_1`).not.toHaveClass("o_campaign_wp_selected");
});

test("campaign_word_picture: remarks editable after the grades are locked", async () => {
    onRpc("web_save", ({ args }) => {
        expect.step(JSON.stringify(args[1].campaign_line_ids));
    });
    await mountView({ type: "form", resModel: "hr.appraisal", resId: 1, arch: ARCH });
    const card = ".o_campaign_wp_criterion:eq(2)";
    await contains(`${card} .o_campaign_wp_level[data-level='4']`).click();
    expect(`${card} .o_campaign_wp_level_2`).toHaveClass("o_campaign_wp_selected");
    expect(`${card} textarea.o_campaign_wp_remarks`).toHaveCount(1);
    expect(".o_campaign_wp_criterion:eq(1) textarea.o_campaign_wp_remarks").toHaveCount(0);
    await contains(`${card} textarea.o_campaign_wp_remarks`).edit("Amended at the meeting");
    await contains(".o_form_button_save").click();
    expect.verifySteps([JSON.stringify([[1, 3, { manager_remarks_ui: "Amended at the meeting" }]])]);
});
