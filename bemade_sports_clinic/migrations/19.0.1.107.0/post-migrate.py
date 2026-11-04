"""Task 1654 — the players already « Urgent » got SUGGESTED critical items.

Task 1677 (19.0.1.117.0): superseded. The items are structured lists now
(name, life-threatening, first aid) and EpiPen is on the player; the
19.0.1.117.0 migration converts the #1654 items in place and the legacy text
itself (a database upgraded from before 19.0.1.107.0 runs both scripts in the
same upgrade, and this one would create items with fields that no longer
exist). Kept as a no-op so the version history stays readable.
"""


def migrate(cr, version):
    return
