"""Task 1630 — allergies + medical alerts replaced the free-text allergies
(one-time conversion of the legacy ``allergies`` text into levels + details).

Task 1677 (19.0.1.117.0): superseded. The allergies and medical alerts are
structured lists now and the levels are computed from them; the
19.0.1.117.0 post-migrate converts the legacy text itself (a database
upgraded from before 19.0.1.99.0 runs both scripts in the same upgrade, and
this one would write levels that are now computed). Kept as a no-op so the
version history stays readable; the classification rules live on in
``models/medical_alerts.py``.
"""


def migrate(cr, version):
    return
