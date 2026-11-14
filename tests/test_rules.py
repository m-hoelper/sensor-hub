import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sensor_hub.rules import run_window_recommendation, build_message

SETTINGS = SimpleNamespace(co2_open_ppm=1200, co2_close_ppm=800, co2_max_ppm=2000,
                           humidity_open_pct=65.0, humidity_close_pct=55.0,
                           humidity_min_pct=30.0, cooldown_min=15, ignore_measurements_older_than_min=5)
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
OPEN, CLOSED = 'OPEN_RECOMMENDED', 'CLOSED'


def last(state, minutes_ago=20):
    return SimpleNamespace(new_state=state, created_at=NOW - timedelta(minutes=minutes_ago))

def reading(co2, humidity, minutes_old=0):
    return SimpleNamespace(co2_ppm=co2, humidity_pct=humidity,
                           created_at=NOW - timedelta(minutes=minutes_old))


@pytest.mark.parametrize(
        ['previous', 'co2', 'humidity', 'expected'],
        [(None,         420,  35,   None),     # no history = CLOSED, fresh air → nothing
         (None,         1300, 40,   OPEN),     # first reading above the limit
         (last(CLOSED), 1200, 40,   OPEN),     # boundary: >= co2_open
         (last(CLOSED), 700,  65,   OPEN),     # mold: humidity >= humidity_open
         (last(CLOSED), 1500, 25,   None),     # too dry blocks the normal CO2 rule
         (last(CLOSED), 2500, 25,   OPEN),     # hard limit wins over "too dry"
         (last(OPEN),   1000, 50,   None),     # inside the band → stay open (hysteresis)
         (last(OPEN),   700,  70,   None),     # CO2 fine but still humid → stay open
         (last(OPEN),   800,  55,   CLOSED),   # boundary: both <= close
         (last(OPEN),   1500, 25,   CLOSED),   # too dry, below the hard limit
         (last(OPEN),   2500, 25,   None),     # too dry, but above the hard limit → stay open
         (last(OPEN),   1500, 40,   None),     # already open, still high → no repeat
         (last(CLOSED, minutes_ago=5),  2500, 45, None),   # inside the cooldown
         (last(CLOSED, minutes_ago=15), 2500, 45, None),   # boundary: exactly cooldown_min still blocks (<=)
         (last(CLOSED, minutes_ago=16), 2500, 45, OPEN)]   # one minute later it's allowed
)
def test_window_recommendation(previous, co2, humidity, expected):

    assert run_window_recommendation(reading(co2, humidity), SETTINGS, previous, NOW) == expected


@pytest.mark.parametrize(
        ['minutes_old', 'expected'],
        [(0,    OPEN),     # live reading
         (4.99, OPEN),     # just inside the window
         (5,    OPEN),     # boundary: exactly ignore_measurements_older_than_min is still fresh (>)
         (5.01, None),     # just too old → backfill, no notification
         (60 * 24, None)]  # a day old (sync after an outage)
)
def test_stale_reading_never_triggers(minutes_old, expected):

    # CO2 far above the hard limit: without the guard this would always open
    assert run_window_recommendation(reading(2500, 45, minutes_old), SETTINGS, None, NOW) == expected


def test_stale_guard_runs_before_state_machine():

    # previous state OPEN + fresh air would normally close — a stale reading must not
    assert run_window_recommendation(reading(700, 50, minutes_old=10), SETTINGS, last(OPEN), NOW) is None


@pytest.mark.parametrize(
        ['state', 'co2', 'humidity', 'start'],
        [(OPEN,   1340, 47.5, 'Open the window: CO2 too high'),
         (OPEN,   900,  68,   'Open the window: too humid'),
         (OPEN,   2500, 25,   'Open the window briefly'),
         (CLOSED, 760,  52,   'Close the window: air is fresh'),
         (CLOSED, 1500, 25,   'Close the window: too dry')]
)
def test_build_message(state, co2, humidity, start):

    assert build_message(state, reading(co2, humidity), SETTINGS).startswith(start)
