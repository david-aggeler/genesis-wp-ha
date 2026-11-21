"""Track compressor cycles from decoded samples for the current local day."""

from dataclasses import dataclass, field
from datetime import date, datetime
from math import isfinite
from statistics import mean

RUN_BANDS = ((60, "good"), (30, "acceptable"), (10, "short"), (6, "very_short"), (0, "short_cycle"))
MEAN_BANDS = ((120, "good"), (60, "acceptable"), (30, "warning"), (0, "bad"))
SHORT_RUN_BANDS = frozenset({"short_cycle", "very_short"})
HEATING = "heating"
HOT_WATER = "hot_water"


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
    def from_dict(cls, day: date, data: dict) -> "DailyRuns | None":
        if data.get("day") != day.isoformat():
            return None
        starts, hot_water_starts, runs = (data.get(key) for key in ("starts", "hot_water_starts", "runs"))
        if (
            type(starts) is not int or type(hot_water_starts) is not int
            or not 0 <= hot_water_starts <= starts or not isinstance(runs, list)
            or len(runs) > starts
        ):
            return None
        if any(
            not isinstance(run, list) or len(run) != 2
            or run[0] not in (HEATING, HOT_WATER)
            or type(run[1]) not in (int, float) or run[1] < 0 or not isfinite(run[1])
            for run in runs
        ):
            return None
        return cls(day, starts, hot_water_starts, [(kind, minutes) for kind, minutes in runs])


# DHF-REQ: genesis-wp-ha/requirement-28
class RunTracker:
    """Observe signal edges and keep completed runs and daily counts."""

    def __init__(self):
        self.daily: DailyRuns | None = None
        self._previous: bool | None = None
        self._open_run: tuple[datetime, str] | None = None
        self._can_restore = True
        self.values: dict[str, int | float | None] = {}

    def add(self, now_local: datetime, signal: bool | None, mode: str | None = None) -> None:
        day = now_local.date()
        if self.daily is None or self.daily.day != day:
            self.daily = DailyRuns(day)
        if signal is True and self._previous is False:
            kind = HOT_WATER if mode == "Hot water" else HEATING
            self._open_run = (now_local, kind)
            self.daily.count_start(kind)
            self._can_restore = False
        elif signal is not True:
            if signal is False and self._open_run is not None:
                started_at, kind = self._open_run
                minutes = (now_local.timestamp() - started_at.timestamp()) / 60
                if minutes >= 0:
                    if started_at.date() != day:
                        self.daily.count_start(kind)
                    self.daily.runs.append((kind, minutes))
            self._open_run = None
        self._previous = signal
        self.values = self.daily.values()

    def restore(self, now_local: datetime, data: dict) -> None:
        """Restore completed observations only, since downtime breaks signal continuity."""
        if self._can_restore and (daily := DailyRuns.from_dict(now_local.date(), data)) is not None:
            self.daily = daily
            self.values = daily.values()
            self._can_restore = False
