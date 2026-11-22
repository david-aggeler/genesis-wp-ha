"""Integrate daily heat from consecutive power samples."""

from dataclasses import dataclass
from datetime import datetime, time
from math import isfinite


def valid_measurement(value):
    if type(value) not in (int, float) or value < 0:
        return False
    try:
        return isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True)
class HeatSample:
    timestamp: float
    power: float | None
    pump_on: bool


# DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-138 genesis-wp-ha/ac-139 genesis-wp-ha/ac-140
class DailyHeat:
    """Accumulate kWh and the observed and integrated pump-running time."""

    def __init__(self):
        self.day = None
        self.energy = self.covered_seconds = self.pump_seconds = 0.0
        self._last = None
        self._restored = False
        self.counted_until = None
        self.rolled_over = False

    # DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-171 genesis-wp-ha/ac-176
    def add(self, now: datetime, power: float | None, pump_on: bool = False):
        """Add the part of the sample interval that falls on the current local date.

        Time up to ``counted_until`` is never counted twice: a sample at or before it (a clock
        step back) only becomes the start of the next pair, so a missing reading still breaks it.
        """
        day = now.date()
        sample = HeatSample(now.timestamp(), power if valid_measurement(power) else None, pump_on)
        previous = self._last
        self._last = sample
        if self.counted_until is not None and sample.timestamp <= self.counted_until:
            return
        if day != self.day:
            self.rolled_over = self.day is not None
            self.day = day
            self.energy = self.covered_seconds = self.pump_seconds = 0.0
        if previous is None:
            self.counted_until = sample.timestamp
            return

        elapsed = sample.timestamp - previous.timestamp
        midnight = datetime.combine(day, time.min, now.tzinfo).timestamp()
        start = max(previous.timestamp, midnight, self.counted_until or previous.timestamp)
        self.counted_until = sample.timestamp
        seconds = sample.timestamp - start
        # Both endpoints must report FR2 on. Long gaps can reduce coverage,
        # but supply no measured energy.
        pump_running = previous.pump_on and sample.pump_on
        if pump_running:
            self.pump_seconds += seconds
        if elapsed > 120 or previous.power is None or sample.power is None:
            return

        # Clip a trapezoid at midnight or at counted time by interpolating power at its start.
        start_power = sample.power + (previous.power - sample.power) * (seconds / elapsed)
        self.energy += (start_power + sample.power) * seconds / 7200
        if pump_running:
            self.covered_seconds += seconds

    # DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-175
    @property
    def coverage(self):
        if not self.pump_seconds:
            return None
        share = 100 * min(1.0, self.covered_seconds / self.pump_seconds)
        return share if isfinite(share) else None

    def take_rollover(self) -> bool:
        """True once after the counters restarted for a new local day."""
        rolled, self.rolled_over = self.rolled_over, False
        return rolled

    def snapshot(self):
        return {
            "day": self.day.isoformat() if self.day is not None else None,
            "energy": self.energy,
            "covered_seconds": self.covered_seconds,
            "pump_seconds": self.pump_seconds,
            "counted_until": self.counted_until,
        }

    # DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-172 genesis-wp-ha/ac-173
    def restore(self, snapshot):
        """Add same-day totals without joining the previous session's sample interval."""
        if self._restored:
            return
        self._restored = True
        if not isinstance(snapshot, dict) or self.day is None or snapshot.get("day") != self.day.isoformat():
            return
        energy = snapshot.get("energy")
        covered = snapshot.get("covered_seconds")
        pump = snapshot.get("pump_seconds")
        if not (all(valid_measurement(value) for value in (energy, covered, pump)) and covered <= pump):
            return
        totals = (self.energy + energy, self.covered_seconds + covered, self.pump_seconds + pump)
        if not all(isfinite(value) for value in totals):
            return
        self.energy, self.covered_seconds, self.pump_seconds = totals
        # The previous session counted up to here; a clock corrected back must not recount it.
        counted = snapshot.get("counted_until")
        if valid_measurement(counted) and counted > (self.counted_until or 0):
            self.counted_until = float(counted)
