import logging

_logger = logging.getLogger(__name__)

# User-visible context prefix of an activity that was scheduled on an injury.
# Fixed fr_CA literal (owner decision, task 1409): fitcrew prod is a fr_CA
# site and the rows are moved in one raw-SQL pass (no ORM, no chatter, no
# notifications). New activities created by the verification cron get the
# same prefix through the translatable sports.patient.injury
# _activity_summary_prefix() helper.
PREFIX_FR = "[Blessure : "
PREFIX_EN = "[Injury: "
PREFIX_HIDDEN = "[Blessure] "   # hidden-from-coaches injuries: no diagnosis in the title (Law 25)


def migrate(cr, version):
    """Move every activity scheduled ON an injury to the injury's PATIENT
    (task 1409: activities live on patients only).

    For each ``mail_activity`` row with ``res_model = 'sports.patient.injury'``
    whose injury still exists:

    * ``res_model_id`` / ``res_model`` / ``res_id`` -> the patient;
    * ``injury_id`` (new technical link, created by the field before this
      post-migrate runs) -> the old ``res_id``;
    * ``summary`` gets the « [Blessure : <diagnostic>] » prefix ONCE
      (rows already carrying a « [Blessure » / « [Injury » prefix keep it).

    Open activities only — done ones are already mail.message rows. Rows
    whose injury no longer exists are left alone (none expected) and
    logged. Raw SQL posts no chatter, so the row counts are logged.
    """
    cr.execute("SELECT id FROM ir_model WHERE model = 'sports.patient'")
    row = cr.fetchone()
    if not row:
        _logger.warning("Task 1409: ir_model row for sports.patient not found; nothing moved")
        return
    patient_model_id = row[0]

    cr.execute(
        """
        UPDATE mail_activity AS a
           SET res_model_id = %(patient_model_id)s,
               res_model    = 'sports.patient',
               res_id       = i.patient_id,
               injury_id    = a.res_id,
               summary      = CASE
                                  WHEN a.summary LIKE %(prefix_fr_like)s
                                    OR a.summary LIKE %(prefix_en_like)s
                                  THEN a.summary
                                  WHEN i.hidden_from_coaches
                                  THEN %(prefix_hidden)s || COALESCE(a.summary, '')
                                  ELSE %(prefix_fr)s || COALESCE(i.diagnosis, '')
                                       || '] ' || COALESCE(a.summary, '')
                              END
          FROM sports_patient_injury AS i
         WHERE a.res_model = 'sports.patient.injury'
           AND i.id = a.res_id
           AND i.patient_id IS NOT NULL
        """,
        {
            "patient_model_id": patient_model_id,
            "prefix_fr": PREFIX_FR,
            "prefix_hidden": PREFIX_HIDDEN,
            # any « [Blessure… » / « [Injury… » prefix (with or without a diagnosis) counts as already prefixed
            "prefix_fr_like": "[Blessure%",
            "prefix_en_like": "[Injury%",
        },
    )
    _logger.info(
        "Task 1409: moved %s injury activities to their patient (injury_id set, "
        "summary prefixed once)",
        cr.rowcount,
    )

    cr.execute(
        "SELECT count(*) FROM mail_activity WHERE res_model = 'sports.patient.injury'"
    )
    left = cr.fetchone()[0]
    if left:
        _logger.warning(
            "Task 1409: %s activities still on sports.patient.injury (injury or "
            "patient missing) — left untouched",
            left,
        )
