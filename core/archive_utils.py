import calendar
from datetime import date


def five_months_ago():
    today = date.today()

    month = today.month - 5
    year = today.year

    while month <= 0:
        month += 12
        year -= 1

    day = min(
        today.day,
        calendar.monthrange(year, month)[1]
    )

    return date(year, month, day)