"""Integrate daily heat from consecutive power samples."""

from dataclasses import dataclass
from datetime import datetime, time
from math import isfinite


def valid_measurement(value):
    return type(value) in (int, float) and isfinite(value) and value >= 0


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

    def add(self, now: datetime, power: float | None, pump_on: bool = False):
        """Add the part of the sample interval that falls on the current local date."""
        day = now.date()
        sample = HeatSample(now.timestamp(), power if valid_measurement(power) else None, pump_on)
        previous = self._last
        if day != self.day:
            self.day = day
            self.energy = self.covered_seconds = self.pump_seconds = 0.0
        self._last = sample
        if previous is None:
            return

        elapsed = sample.timestamp - previous.timestamp
        if elapsed <= 0:
            return
        midnight = datetime.combine(day, time.min, now.tzinfo).timestamp()
        seconds = sample.timestamp - max(previous.timestamp, midnight)
        # Both endpoints must report FR2 on. Long gaps can reduce coverage,
        # but supply no measured energy.
        pump_running = previous.pump_on and sample.pump_on
        if pump_running:
            self.pump_seconds += seconds
        if elapsed > 120 or previous.power is None or sample.power is None:
            return

        # Clip a midnight-crossing trapezoid by interpolating power at midnight.
        start_power = sample.power + (previous.power - sample.power) * (seconds / elapsed)
        self.energy += (start_power + sample.power) * seconds / 7200
        if pump_running:
            self.covered_seconds += seconds

    @property
    def coverage(self):
        if self.pump_seconds:
            return 100 * self.covered_seconds / self.pump_seconds
        return None

    def snapshot(self):
        return {
            "day": self.day.isoformat() if self.day is not None else None,
            "energy": self.energy,
            "covered_seconds": self.covered_seconds,
            "pump_seconds": self.pump_seconds,
        }

    def restore(self, snapshot):
        """Add same-day totals without joining the previous session's sample interval."""
        if self._restored:
            return
        self._restored = True
        if self.day is None or snapshot.get("day") != self.day.isoformat():
            return
        energy = snapshot.get("energy")
        covered = snapshot.get("covered_seconds")
        pump = snapshot.get("pump_seconds")
        if all(valid_measurement(value) for value in (energy, covered, pump)) and covered <= pump:
            self.energy += energy
            self.covered_seconds += covered
            self.pump_seconds += pump
