"""Track compressor cycles from decoded samples for the current local day."""

from dataclasses import dataclass, field
from datetime import date, datetime
from math import isfinite
from statistics import mean
from sys import float_info
from time import monotonic

RUN_BANDS = ((60, "good"), (30, "acceptable"), (10, "short"), (6, "very_short"), (0, "short_cycle"))
MEAN_BANDS = ((120, "good"), (60, "acceptable"), (30, "warning"), (0, "bad"))
SHORT_RUN_BANDS = frozenset({"short_cycle", "very_short"})
HEATING = "heating"
HOT_WATER = "hot_water"
# Far above any real day (one start per 30 s poll is 2880); bounds restored counts so the
# published state stays within Home Assistant's 255-character limit (ac-169).
MAX_DAILY_STARTS = 100_000
# Local dates kept, so a corrected clock jump across midnight finds its day again (ac-168).
KEPT_DAYS = 2


def run_band(minutes: float) -> str:
    return next(label for minimum, label in RUN_BANDS if minutes >= minimum)


def mean_band(minutes: float) -> str:
    return next(label for minimum, label in MEAN_BANDS if minutes >= minimum)


@dataclass
class DailyRuns:
    """Starts observed and runs completed on a local date."""

    day: date
    starts: int = 0
    hot_water_starts: int = 0
    runs: list[tuple[str, float]] = field(default_factory=list)

    def count_start(self, kind: str) -> None:
        self.starts += 1
        if kind == HOT_WATER:
            self.hot_water_starts += 1

    def values(self) -> dict[str, int | float | None]:
        heating = [minutes for kind, minutes in self.runs if kind == HEATING]
        return {
            "starts_today": self.starts,
            "hot_water_starts_today": self.hot_water_starts,
            "short_heating_runs_today": sum(run_band(minutes) in SHORT_RUN_BANDS for minutes in heating),
            "running_hours_today": sum(minutes for _, minutes in self.runs) / 60,
            "heating_run_minimum": min(heating, default=None),
            "heating_run_mean": mean(heating) if heating else None,
            "heating_run_maximum": max(heating, default=None),
            "last_run_length": self.runs[-1][1] if self.runs else None,
        }

    def as_dict(self) -> dict:
        return {
            "day": self.day.isoformat(),
            "starts": self.starts,
            "hot_water_starts": self.hot_water_starts,
            "runs": [list(run) for run in self.runs],
        }

    @classmethod
    def from_dict(cls, day: date, data: object) -> "DailyRuns | None":
        if not isinstance(data, dict) or data.get("day") != day.isoformat():
            return None
        starts, hot_water_starts, runs = (data.get(key) for key in ("starts", "hot_water_starts", "runs"))
        if (
            type(starts) is not int or type(hot_water_starts) is not int
            or not 0 <= hot_water_starts <= starts <= MAX_DAILY_STARTS or not isinstance(runs, list)
            or len(runs) > starts
        ):
            return None
        if any(
            not isinstance(run, list) or len(run) != 2
            or run[0] not in (HEATING, HOT_WATER)
            or type(run[1]) not in (int, float) or not 0 <= run[1] <= float_info.max
            for run in runs
        ):
            return None
        # Every completed run needs a counted start of its own kind (ac-167).
        hot_water_runs = sum(run[0] == HOT_WATER for run in runs)
        if hot_water_runs > hot_water_starts or len(runs) - hot_water_runs > starts - hot_water_starts:
            return None
        durations = [(kind, float(minutes)) for kind, minutes in runs]
        if not isfinite(sum(minutes for _, minutes in durations)):
            return None
        return cls(day, starts, hot_water_starts, durations)


# DHF-REQ: genesis-wp-ha/requirement-28
class RunTracker:
    """Observe signal edges and keep completed runs and daily counts."""

    def __init__(self):
        self.daily: DailyRuns | None = None
        self._days: dict[date, DailyRuns] = {}
        self._previous: bool | None = None
        self._open_run: tuple[date, float, str] | None = None
        self.values: dict[str, int | float | None] = {}

    def _select(self, day: date) -> bool:
        """Publish the observations of ``day``; report whether the published day changed.

        Observations are kept per local date (the latest ``KEPT_DAYS``), so a clock step in
        either direction across midnight returns to that date's counts (ac-160, ac-164, ac-168).
        """
        if day not in self._days:
            self._days[day] = DailyRuns(day)
            for old in sorted(self._days)[:-KEPT_DAYS]:
                del self._days[old]
        daily = self._days.get(day)
        if daily is None:  # older than every kept date: observe it without publishing
            daily = DailyRuns(day)
        changed = daily is not self.daily
        self.daily = daily
        return changed

    def add(self, now_local: datetime, signal: bool | None, mode: str | None = None) -> bool:
        """Record a sample on its local date and report whether the published snapshot changed."""
        day = now_local.date()
        changed = self._select(day)
        if signal is True and self._previous is False:
            kind = HOT_WATER if mode == "Hot water" else HEATING
            self._open_run = (day, monotonic(), kind)
            self.daily.count_start(kind)
            changed = True
        elif signal is not True:
            if signal is False and self._open_run is not None:
                start_day, started_at, kind = self._open_run
                minutes = (monotonic() - started_at) / 60
                if start_day != day:  # started on another date: the run counts on its end day (ac-134)
                    self.daily.count_start(kind)
                self.daily.runs.append((kind, minutes))
                changed = True
            self._open_run = None
        self._previous = signal
        if changed:
            self.values = self.daily.values()
        return changed

    def restore(self, now_local: datetime, data: object) -> None:
        """Seed daily observations before polling begins."""
        if (daily := DailyRuns.from_dict(now_local.date(), data)) is not None:
            self._days = {daily.day: daily}
            self.daily = daily
            self.values = daily.values()
