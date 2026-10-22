"""Whether an iCalendar VEVENT occupies someone's time, and when.

Pure helpers over ``icalendar`` components, shared by every module that reads
or writes calendar events so they all reach the same answer.
"""

from datetime import date, datetime, time, timedelta

import pytz

TRANSPARENT = "TRANSPARENT"
OPAQUE = "OPAQUE"


def _normalize_address(address):
    address = str(address or "").strip().lower()
    return address.removeprefix("mailto:")


def _attendees(vevent):
    attendees = vevent.get("ATTENDEE") or []
    return attendees if isinstance(attendees, list) else [attendees]


def is_busy(vevent, email=None):
    """True when ``vevent`` occupies the time of the person at ``email``.

    Not busy: shown as free (TRANSP:TRANSPARENT), cancelled, or declined by
    that person. Without ``email``, attendees are not consulted.
    """
    if str(vevent.get("TRANSP", OPAQUE)).upper() == TRANSPARENT:
        return False
    if str(vevent.get("STATUS", "")).upper() == "CANCELLED":
        return False
    if email:
        person = _normalize_address(email)
        for attendee in _attendees(vevent):
            if (
                _normalize_address(attendee) == person
                and str(attendee.params.get("PARTSTAT", "")).upper() == "DECLINED"
            ):
                return False
    return True


def transp_to_show_as(transp):
    """Map an iCalendar TRANSP value to ``calendar.event.show_as``."""
    return "free" if str(transp or "").upper() == TRANSPARENT else "busy"


def show_as_to_transp(show_as):
    """Map ``calendar.event.show_as`` to an iCalendar TRANSP value."""
    return TRANSPARENT if show_as == "free" else OPAQUE


def _to_naive_utc(value, tz):
    if value.tzinfo is None:
        value = pytz.timezone(tz or "UTC").localize(value)
    return value.astimezone(pytz.utc).replace(tzinfo=None)


def busy_interval(vevent, tz=None):
    """Return ``(start, stop, allday)`` for ``vevent``.

    Timed events: naive UTC datetimes; a floating time is read in ``tz``
    (UTC when not given). All-day events: midnight of the first day and of
    the day after the last one (stop is exclusive), not converted.
    """
    start = vevent.decoded("DTSTART")
    if "DTEND" in vevent:
        stop = vevent.decoded("DTEND")
    elif "DURATION" in vevent:
        stop = start + vevent.decoded("DURATION")
    else:
        # RFC 5545 §3.6.1: a DATE start lasts one day, a DATE-TIME start none.
        stop = start + timedelta(days=1) if not isinstance(start, datetime) else start

    if not isinstance(start, datetime) and isinstance(start, date):
        return (
            datetime.combine(start, time.min),
            datetime.combine(stop, time.min),
            True,
        )
    return _to_naive_utc(start, tz), _to_naive_utc(stop, tz), False
