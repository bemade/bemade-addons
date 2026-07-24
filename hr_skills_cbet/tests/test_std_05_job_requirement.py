"""UC-STD-05 — Job position requirements.

AC1: hr.job.skill row with the qualification skill; the native missing/expiring
     certification cron handles activities with no extra code.
This test verifies the tie-back skill plugs into the native hr.job.skill model.
"""
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestStdJobRequirement(CbetCommon):
    def test_tieback_skill_usable_as_job_requirement(self):
        skill = self._make_cert_skill("Tech Classe I")
        job = self.env["hr.job"].create({"name": "Water Treatment Technician"})
        level = skill.skill_type_id.skill_level_ids[:1]
        job_skill = self.env["hr.job.skill"].create({
            "job_id": job.id,
            "skill_type_id": skill.skill_type_id.id,
            "skill_id": skill.id,
            "skill_level_id": level.id,
        })
        self.assertTrue(job_skill.is_certification)
        self.assertIn(job_skill, job.job_skill_ids)
