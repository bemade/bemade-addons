{
    "name": "CBET / TWI Competency & Certification Engine",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Skills Management",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "maintainer": "Denis Durepos",
    "summary": "Competency catalog, qualification standards, signed evaluations,"
               " and time-limited certifications on top of hr_skills.",
    "description": """
CBET / TWI Competency & Certification Engine
============================================

A generic, resellable competency-based education and training (CBET) / Training
Within Industry (TWI) engine extending the Odoo 19.0 hr / hr_skills stack.

- Competency catalog: coded competencies with a typed prerequisite graph,
  sequenced performance criteria, oral knowledge questions, multiple evaluation
  units, per-competency protocol and validity policy, and a draft-to-published
  lifecycle with immutable version snapshots.
- Qualification standards: full requirement set computed as the transitive
  closure of obligatory prerequisites; per-employee qualification state with
  automatic suspension and restoration, tied back to a coarse hr.skill
  certification on hr.employee.skill.
- Signed evaluations: two-part (practical criteria and oral questions),
  snapshotted from the published competency, computed pass indicators, dual
  evaluator and technician signatures with locking, targeted retake
  (reprise ciblee), and evidence retention.
- Certifications and validity: time-limited competency certifications with an
  expiry engine and activity nudges; qualification-level early warning rides
  the native hr.employee.skill cron.
- Reports: a printable evaluation grid and an employees-by-competencies
  training matrix.

Content-agnostic; competency content is seeded separately.
""",
    "depends": [
        "hr",
        "hr_skills",
    ],
    "data": [
        "security/hr_skills_cbet_groups.xml",
        "security/ir.model.access.csv",
        "security/cbet_record_rules.xml",
        "data/cbet_cron.xml",
        "report/cbet_evaluation_report.xml",
        "views/cbet_domain_views.xml",
        "views/cbet_competency_views.xml",
        "views/cbet_standard_views.xml",
        "views/cbet_evaluation_views.xml",
        "views/cbet_certification_views.xml",
        "views/cbet_qualification_views.xml",
        "views/cbet_matrix_views.xml",
        "views/res_config_settings_views.xml",
        "views/cbet_menus.xml",
    ],
    "application": True,
    "installable": True,
}
