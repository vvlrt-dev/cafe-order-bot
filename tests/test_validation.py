from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from bot.validation import (ValidationError, clean_name, clean_phone, earliest_pickup,
                            parse_pickup_time, pickup_slots)

TZ = ZoneInfo("Asia/Tashkent")
OPEN, CLOSE = time(10, 0), time(22, 0)


def at(h, m):
    return datetime(2026, 11, 14, h, m, tzinfo=TZ)


@pytest.mark.parametrize("raw, expected", [("  Aziza  ", "Aziza"), ("John   Smith", "John Smith")])
def test_clean_name_ok(raw, expected):
    assert clean_name(raw) == expected


@pytest.mark.parametrize("raw", ["", "A", "1234", "x" * 41])
def test_clean_name_rejects(raw):
    with pytest.raises(ValidationError):
        clean_name(raw)


@pytest.mark.parametrize("raw, expected", [
    ("+998 90 123-45-67", "+998901234567"),
    ("(555) 010 2030", "5550102030"),
])
def test_clean_phone_ok(raw, expected):
    assert clean_phone(raw) == expected


@pytest.mark.parametrize("raw", ["call me", "12345", "+1234567890123456", "90-12-ab"])
def test_clean_phone_rejects(raw):
    with pytest.raises(ValidationError):
        clean_phone(raw)


def test_earliest_pickup_adds_prep_and_rounds_up():
    assert earliest_pickup(at(12, 7), OPEN, 20) == at(12, 30)


def test_earliest_pickup_before_opening_is_opening_time():
    assert earliest_pickup(at(8, 0), OPEN, 20) == at(10, 0)


def test_pickup_slots_stop_at_closing():
    assert pickup_slots(at(21, 20), OPEN, CLOSE, 20) == [at(21, 45), at(22, 0)]
    assert pickup_slots(at(21, 50), OPEN, CLOSE, 20) == []


def test_parse_pickup_time_ok():
    assert parse_pickup_time("18.30", at(12, 7), OPEN, CLOSE, 20) == at(18, 30)


@pytest.mark.parametrize("raw, message", [
    ("soon", "HH:MM"),
    ("25:00", "not a valid time"),
    ("09:30", "10:00–22:00"),
    ("12:15", "at least 20 minutes"),
])
def test_parse_pickup_time_rejects(raw, message):
    with pytest.raises(ValidationError, match=message):
        parse_pickup_time(raw, at(12, 7), OPEN, CLOSE, 20)
