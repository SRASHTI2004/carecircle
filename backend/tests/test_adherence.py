from datetime import datetime, timedelta

from app.services.adherence import (
    DUE, MISSED, SKIPPED, TAKEN_LATE, TAKEN_ON_TIME, UPCOMING, adherence_percent, classify, slots_for,
)

S = datetime(2025, 1, 10, 8, 0)


def test_classify_taken_on_time_and_late():
    assert classify(S, "taken", S + timedelta(minutes=10), S + timedelta(hours=1)) == TAKEN_ON_TIME
    assert classify(S, "taken", S + timedelta(minutes=30), S + timedelta(hours=1)) == TAKEN_ON_TIME
    assert classify(S, "taken", S + timedelta(minutes=31), S + timedelta(hours=1)) == TAKEN_LATE
    assert classify(S, "taken", S - timedelta(minutes=20), S) == TAKEN_ON_TIME  # early is fine


def test_classify_unlogged_by_time():
    assert classify(S, None, None, S - timedelta(minutes=1)) == UPCOMING
    assert classify(S, None, None, S) == DUE
    assert classify(S, None, None, S + timedelta(minutes=30)) == DUE
    assert classify(S, None, None, S + timedelta(minutes=31)) == MISSED


def test_classify_skipped():
    assert classify(S, "skipped", S, S + timedelta(hours=5)) == SKIPPED


def test_adherence_percent():
    assert adherence_percent({}) is None
    assert adherence_percent({TAKEN_ON_TIME: 8, TAKEN_LATE: 1, MISSED: 1}) == 90
    assert adherence_percent({SKIPPED: 2, TAKEN_ON_TIME: 2}) == 50


def test_slots_respect_dates_and_times():
    med = {"times": '["08:00","20:00"]', "start_date": "2025-01-10", "end_date": "2025-01-11"}
    slots = slots_for(med, datetime(2025, 1, 9).date(), datetime(2025, 1, 15).date())
    assert [s.strftime("%d %H:%M") for s in slots] == ["10 08:00", "10 20:00", "11 08:00", "11 20:00"]
