"""Task 1653 — players whose allergy / medical-alert level is « None known »
but who still carry details (or EpiPen) predate the rule « None known clears
and locks them ». Their data is left as is; they are flagged « to validate »
(medical_alert_review) so MC's next choice applies the rule. Idempotent; logs
the count only."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE sports_patient
           SET medical_alert_review = TRUE
         WHERE COALESCE(medical_alert_review, FALSE) = FALSE
           AND (   (allergy_level = 'none'
                    AND (COALESCE(allergy_details, '') <> '' OR COALESCE(allergy_epipen, FALSE)))
                OR (medical_alert_level = 'none' AND COALESCE(medical_alert_details, '') <> ''))
    """)
    _logger.info("Task 1653: %d player(s) at « None known » with details / EpiPen flagged to validate",
                 cr.rowcount)
