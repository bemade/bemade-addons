"""Use case 2 — scores, rating levels and alignment from the campaign's thresholds.

Acceptance criteria (5-level scale; sections of 2 and 3 criteria → /10, /15, /25):
- Self, manager and final (calibrated) totals, per section and overall, with maxima
  = number of criteria × the scale's highest value, and percentages.
- The overall rating level is the highest level whose threshold the FINAL total
  reaches; below every threshold → the lowest level (edges included).
- Each section has its own rating from its own thresholds.
- Alignment: |final − self| ≤ the campaign's gap → aligned, else « to discuss ».
- Thresholds are the campaign's (changing them changes the result of that campaign).
- Ratings stay empty until every criterion of the section (or of the evaluation) is
  graded; a scope without thresholds has no rating.
"""

from odoo.tests import tagged

from .common import CampaignCase


@tagged("post_install", "-at_install")
class TestScores(CampaignCase):
    def setUp(self):
        super().setUp()
        self.set_thresholds(self.campaign, None, {5: 22, 4: 18, 3: 12, 2: 8})
        self.set_thresholds(self.campaign, self.sections[0], {5: 9, 4: 7, 3: 5, 2: 3})
        self.set_thresholds(self.campaign, self.sections[1], {5: 13, 4: 11, 3: 8, 2: 5})
        self.campaign.alignment_gap = 2
        self.campaign.target_score = 18
        self.appraisal = self.launch()
        lines = self.appraisal.campaign_line_ids
        self.s1 = lines.filtered(lambda l: l.section_id == self.sections[0])
        self.s2 = lines.filtered(lambda l: l.section_id == self.sections[1])

    @staticmethod
    def grades_for(lines, total, top=5):
        n = len(lines)
        assert n <= total <= top * n
        grades = [1] * n
        rest = total - n
        for i in range(n):
            add = min(top - 1, rest)
            grades[i] += add
            rest -= add
        return grades

    def _final(self, s1_total, s2_total):
        for lines, total in ((self.s1, s1_total), (self.s2, s2_total)):
            for line, grade in zip(lines, self.grades_for(lines, total)):
                line.sudo().write({"manager_grade": grade, "calibrated_grade": grade})

    def _self(self, s1_total, s2_total):
        for lines, total in ((self.s1, s1_total), (self.s2, s2_total)):
            for line, grade in zip(lines, self.grades_for(lines, total)):
                line.sudo().write({"employee_grade": grade})

    def _level(self, value):
        return self.scale.level_ids.filtered(lambda lv: lv.value == value)

    def _section_band(self, section):
        result = self.appraisal.sudo()._campaign_results_data()
        row = next(r for r in result["sections"] if r["section"] == section)
        return row["band"]

    def test_overall_band_edges(self):
        a = self.appraisal.sudo()
        for (s1, s2), value in [
            ((9, 13), 5), ((9, 12), 4),     # 22 / 21
            ((7, 11), 4), ((7, 10), 3),     # 18 / 17
            ((5, 7), 3), ((4, 7), 2),       # 12 / 11
            ((3, 5), 2), ((2, 5), 1),       # 8 / 7
        ]:
            self._final(s1, s2)
            self.assertEqual(a.score_final_total, s1 + s2)
            self.assertEqual(a.band_final_id, self._level(value), f"total {s1 + s2}")

    def test_section_band_edges(self):
        for s1, value in [(9, 5), (8, 4), (7, 4), (6, 3), (5, 3), (4, 2), (3, 2), (2, 1)]:
            self._final(s1, 10)
            self.assertEqual(self._section_band(self.sections[0]), self._level(value), f"s1 {s1}")
        for s2, value in [(13, 5), (12, 4), (11, 4), (8, 3), (7, 2), (5, 2), (4, 1)]:
            self._final(5, s2)
            self.assertEqual(self._section_band(self.sections[1]), self._level(value), f"s2 {s2}")

    def test_alignment_gap(self):
        a = self.appraisal.sudo()
        self._self(5, 8)        # 13
        self._final(6, 9)       # 15 → gap 2
        self.assertEqual(a.score_gap, 2)
        self.assertEqual(a.score_aligned, "aligned")
        self._final(6, 10)      # 16 → gap 3
        self.assertEqual(a.score_aligned, "discuss")
        self._final(4, 6)       # 10 → gap -3
        self.assertEqual(a.score_gap, -3)
        self.assertEqual(a.score_aligned, "discuss")

    def test_sub_totals_maxima_and_percent(self):
        self._self(10, 15)
        self._final(6, 9)
        data = self.appraisal.sudo()._campaign_results_data()
        rows = {r["section"]: r for r in data["sections"]}
        self.assertEqual((rows[self.sections[0]]["self"], rows[self.sections[0]]["max"]), (10, 10))
        self.assertEqual((rows[self.sections[1]]["final"], rows[self.sections[1]]["max"]), (9, 15))
        self.assertEqual((data["total"]["self"], data["total"]["final"], data["total"]["max"]),
                         (25, 15, 25))
        ui = self.appraisal.with_user(self.hr_user)
        self.assertEqual(ui.campaign_max_total, 25)
        self.assertAlmostEqual(ui.ui_final_percent, 60.0)
        self.assertEqual(ui.ui_target_score, 18)

    def test_campaign_thresholds_drive_the_result(self):
        self._final(5, 10)  # 15 → level 3
        self.assertEqual(self.appraisal.sudo().band_final_id, self._level(3))
        self.set_thresholds(self.campaign, None, {5: 15})
        self.assertEqual(self.appraisal.sudo().band_final_id, self._level(5))

    def test_band_empty_until_complete_or_without_thresholds(self):
        self.s1[:1].sudo().write({"manager_grade": 5, "calibrated_grade": 5})
        self.assertFalse(self.appraisal.sudo().band_final_id)
        self.assertFalse(self._section_band(self.sections[0]))
        self._final(5, 10)
        self.campaign.threshold_ids.filtered(lambda t: t.section_id == self.sections[1]).unlink()
        self.assertFalse(self._section_band(self.sections[1]))
        self.assertTrue(self._section_band(self.sections[0]))
