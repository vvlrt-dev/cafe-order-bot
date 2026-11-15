"""Validation for the checkout fields: name, phone and pickup time."""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta

_PHONE_ALLOWED = re.compile(r"^\+?[\d\s\-()]+$")
_TIME = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")


class ValidationError(ValueError):
    """Raised with a message that can be shown to the customer as is."""


def clean_name(text: str) -> str:
    name = " ".join(text.split())
    if len(name) < 2:
        raise ValidationError("Please enter a name with at least 2 letters.")
    if len(name) > 40:
        raise ValidationError("That name is a bit long. Please keep it under 40 characters.")
    if not any(ch.isalpha() for ch in name):
        raise ValidationError("A name should contain letters.")
    return name


def clean_phone(text: str) -> str:
    raw = text.strip()
    if not _PHONE_ALLOWED.match(raw):
        raise ValidationError("Please send a phone number using digits, for example +998 90 123 45 67.")
    digits = re.sub(r"\D", "", raw)
    if not 7 <= len(digits) <= 15:
        raise ValidationError("A phone number should have 7 to 15 digits.")
    return f"+{digits}" if raw.startswith("+") else digits


def round_up(moment: datetime, step_minutes: int = 15) -> datetime:
    moment = moment.replace(second=0, microsecond=0)
    extra = (-moment.minute) % step_minutes
    return moment + timedelta(minutes=extra)


def earliest_pickup(now: datetime, opens_at: time, prep_minutes: int) -> datetime:
    """First pickup moment today: after preparation time and not before opening."""
    ready = round_up(now + timedelta(minutes=prep_minutes))
    opening = now.replace(hour=opens_at.hour, minute=opens_at.minute, second=0, microsecond=0)
    return max(ready, opening)


def pickup_slots(now: datetime, opens_at: time, closes_at: time, prep_minutes: int, count: int = 4) -> list[datetime]:
    """Suggested pickup times for today, every 15 minutes from the earliest possible one."""
    closing = now.replace(hour=closes_at.hour, minute=closes_at.minute, second=0, microsecond=0)
    slot = earliest_pickup(now, opens_at, prep_minutes)
    slots = []
    while slot <= closing and len(slots) < count:
        slots.append(slot)
        slot += timedelta(minutes=15)
    return slots


def parse_pickup_time(text: str, now: datetime, opens_at: time, closes_at: time, prep_minutes: int) -> datetime:
    match = _TIME.match(text)
    if not match:
        raise ValidationError("Please send the time as HH:MM, for example 18:30.")
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        raise ValidationError("That is not a valid time. Please use HH:MM, for example 18:30.")
    pickup = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    opening = now.replace(hour=opens_at.hour, minute=opens_at.minute, second=0, microsecond=0)
    closing = now.replace(hour=closes_at.hour, minute=closes_at.minute, second=0, microsecond=0)
    if pickup < opening or pickup > closing:
        raise ValidationError(f"We take orders for {opens_at:%H:%M}–{closes_at:%H:%M}. Please choose a time in that window.")
    earliest = now + timedelta(minutes=prep_minutes)
    if pickup < earliest.replace(second=0, microsecond=0):
        raise ValidationError(f"We need at least {prep_minutes} minutes to prepare. The earliest time is {round_up(earliest):%H:%M}.")
    return pickup
