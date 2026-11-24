{
    "name": "Appraisal Campaigns",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Appraisals",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "maintainer": "Denis Durepos",
    "summary": "Yearly evaluation campaigns on Odoo Appraisals: configurable rating scale, "
    "sections and word-picture criteria, calibration matrix, meeting and acknowledgement.",
    "description": """
Appraisal Campaigns
===================

Runs a company-wide performance evaluation campaign on top of Odoo Appraisals,
with a fixed flow (self-evaluation → manager evaluation → calibration → meeting →
acknowledgement → closed) and a grading model each company configures.

**Rating scale** — HR defines the scale: any number of levels, each with a value
(1, 2, 3…) and a translatable name (e.g. *Unsatisfactory* … *Superior*). The scale
also holds the default overall thresholds, target score and alignment gap that new
campaigns start from.

**Sections** — criteria are grouped in ordered, translatable sections (e.g. *Core
values*, *Job performance*). Each section has its own default rating thresholds,
expressed in points: « level X from N points ».

**Criteria catalogue** — each criterion belongs to a section and carries a
description and one *word picture* per level of the scale (translatable). HR edits
the catalogue; every appraisal keeps a frozen copy of the wording it was graded with,
in every installed language.

**Campaign** — HR creates a campaign (period, deadlines, scale, thresholds, target
score, alignment gap), picks the employees and launches it: each employee with an
Odoo user gets an appraisal with the catalogue's criteria and a to-do. The campaign
keeps its own thresholds, so a year keeps its own rules.

**Workflow** —

1. *Self-evaluation*: the employee grades each criterion by clicking the word picture
   that fits (all levels are shown side by side) and gives examples, then submits.
2. *Manager evaluation*: the evaluator sees the self-evaluation, grades independently
   with the same cards and adds remarks, then submits for calibration. The manager's
   grades are then locked; the remarks stay editable by the evaluator (and HR) through
   the calibration and the meeting until the employee acknowledges the evaluation.
   Every remark change after the submission is logged (« Remark Changes », HR only,
   never in the chatter, which the employee follows).
3. *Calibration*: the « Calibrate evaluations » group compares the grades of the whole
   campaign on the calibration board — a pivot matrix with one row per employee and
   one column per criterion (catalogue order), each cell the final grade. Clicking a
   cell opens the grade to calibrate: new grade, mandatory note, change log. HR closes
   the calibration.
4. *Meeting*: the evaluator presents the evaluation from their own screen or the
   printout, may amend a remark, then clicks « Meeting held — share with the
   employee ». Only then does the employee see the evaluation in Odoo.
5. *Acknowledgement*: the employee confirms « I have read and discussed this
   evaluation » (timestamped, optional comment), which freezes the remarks, and the
   evaluator validates.
6. *HR close*: the appraisal is locked and the evaluation PDF is attached.

**Scores** — self, manager and final (calibrated) totals per section and overall,
percentages, section and overall rating levels from the campaign's thresholds, and the
self/final gap (« aligned » or « to discuss »).

**Confidentiality** — enforced on the server: before « Meeting held » the employee
reads nothing of the manager's or final evaluation (form, printout, chatter, to-dos,
e-mails) and never any calibration note; the evaluator reads the self-evaluation once
it is submitted; the calibration matrix is readable only by HR and the calibration
group.

**Extension points** — ``_campaign_render_text`` / ``_campaign_render_html`` on
``hr.appraisal.campaign`` (wording of to-dos and chatter notes) and
``_campaign_after_self_eval_steps`` on ``hr.appraisal`` (an action chained after the
self-evaluation, e.g. a questionnaire).

No data is shipped: a company module (or HR) creates the scale, sections and criteria.
""",
    "depends": ["hr_appraisal", "mail"],
    "data": [
        "security/hr_appraisal_campaign_security.xml",
        "security/ir.model.access.csv",
        "report/hr_appraisal_campaign_report.xml",
        "views/hr_appraisal_campaign_scale_views.xml",
        "views/hr_appraisal_campaign_criterion_views.xml",
        "views/hr_appraisal_campaign_line_views.xml",
        "views/hr_appraisal_views.xml",
        "views/hr_appraisal_campaign_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "hr_appraisal_campaign/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "hr_appraisal_campaign/static/tests/**/*.test.js",
        ],
        "web.assets_tests": [
            "hr_appraisal_campaign/static/tests/tours/*.js",
        ],
    },
    "installable": True,
}
