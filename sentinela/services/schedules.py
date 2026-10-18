from datetime import timedelta, timezone
from zoneinfo import ZoneInfo


def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def in_schedule(now, timezone_name, start, end, weekdays):
    local = as_utc(now).astimezone(ZoneInfo(timezone_name))
    clock = local.strftime("%H:%M")
    day = local.weekday()
    if start == end:
        allowed = True
    elif start < end:
        allowed = start <= clock < end
    else:
        allowed = clock >= start or clock < end
        if clock < end:
            day = (local - timedelta(days=1)).weekday()
    return allowed and str(day) in weekdays.split(",")
