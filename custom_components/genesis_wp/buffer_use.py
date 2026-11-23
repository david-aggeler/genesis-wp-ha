"""Evaluate heating-buffer discharge phases from decoded library samples."""

from dataclasses import dataclass
from datetime import date, datetime
from math import isclose, isfinite
from statistics import median

from genesis_wp import const as c
from genesis_wp.derived import HC2_BUFFER, HC2_PUMP

COMPRESSOR = c.ATTR_DINPUT_COMPRESSOR_CONTROL_SIGNAL
MODE = c.ATTR_INPUT_FIRST_PRIORITISED_DEMAND
PASSIVE_COOLING = c.ATTR_DINPUT_INDICATION_WHEN_MIXING_VALVE_1_IS_PRODUCING_PASSIVE_COOLING
CIRCUIT_TARGET = c.ATTR_INPUT_DESIRED_TEMPERATURE_DISTRIBUTION_CIRCUIT_MIX_VALVE_1
BUFFER_TARGET = c.ATTR_INPUT_BUFFER_TANK_CHARGE_SET_POINT
PHASE_INPUTS = (COMPRESSOR, MODE, HC2_PUMP, PASSIVE_COOLING, CIRCUIT_TARGET, *HC2_BUFFER)
CURVE_INPUTS = (BUFFER_TARGET, CIRCUIT_TARGET)

# Conservative bounds for the decoded centi-degree inputs. The full signed
# temperature span is under 656 K, and the smallest positive mean drop is 0.005 K.
MAX_RESTART_MARGIN = 656
MAX_COLD_TAIL_SHARE = 13_120_000


@dataclass(frozen=True)
class Discharge:
    margin: float
    share: float
    energy: float | None


# DHF-REQ: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-142 genesis-wp-ha/ac-143
class BufferUseEvaluator:
    """Track complete compressor pauses and aggregate phases by local restart day."""

    def __init__(self, volume: float | None, offset: float | None):
        self.volume = volume
        self.offset = offset
        self.day: date | None = None
        self.last: Discharge | None = None
        self.phases: list[tuple[float, float]] = []
        self._signal: bool | None = None
        self._stop: float | None = None

    def roll_day(self, now: datetime) -> bool:
        if now.date() == self.day:
            return False
        self.day = now.date()
        self.phases.clear()
        return True

    def add(self, now: datetime, data: dict) -> None:
        self.roll_day(now)
        previous = self._signal
        self._signal = data.get(COMPRESSOR)
        if (
            self._signal is None
            or data.get(HC2_PUMP) is not True
            or data.get(PASSIVE_COOLING) is not False
            or data.get(MODE) in (None, "Hot water")
        ):
            self._stop = None
            return

        if previous is True and self._signal is False:
            self._stop = self._temperature(data)
        elif self._signal is True:
            if previous is False and self._stop is not None:
                self._finish(data)
            self._stop = None

    @staticmethod
    def _temperature(data: dict) -> float | None:
        buffer, supply = (data.get(key) for key in HC2_BUFFER)
        if buffer is None or supply is None:
            return None
        return (buffer + supply) / 2

    def _finish(self, data: dict) -> None:
        restart = self._temperature(data)
        target = data.get(CIRCUIT_TARGET)
        if restart is None or target is None:
            return
        # The mean of two centi-degree readings is exact to half a centi-degree.
        margin = round(restart - target, 3)
        drop = round(self._stop - restart, 3)
        share = 100 * max(0, -margin) / drop if drop > 0 else 0.0
        energy = None
        if self.volume is not None:
            converted = self.volume * (drop * (4.18 / 3600))
            if isfinite(converted):
                energy = converted
        self.last = Discharge(margin, share, energy)
        self.phases.append((margin, share))

    @property
    def daily(self) -> tuple[float | None, float | None]:
        if not self.phases:
            return None, None
        margins, shares = zip(*self.phases)
        # A median can halve the 0.005 K resolution of a phase margin.
        return round(median(margins), 4), median(shares)

    # DHF-REQ: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-144
    @property
    def judgement(self) -> str | None:
        if self.offset is None or not self.phases:
            return None
        margin, share = self.daily
        # Division and the median of two ratios can round just above the limit.
        if margin < 0 or (share > 15 and not isclose(share, 15, rel_tol=0, abs_tol=1e-12)):
            return "raise"
        return "lower" if margin > self.offset else "keep"

    # DHF-REQ: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-146
    def snapshot(self) -> dict:
        return {
            "day": self.day.isoformat() if self.day else None,
            "phases": [list(phase) for phase in self.phases],
        }

    def restore(self, now: datetime, snapshot: object) -> None:
        self.roll_day(now)
        if not isinstance(snapshot, dict) or snapshot.get("day") != now.date().isoformat():
            return
        phases = snapshot.get("phases")
        if not isinstance(phases, list):
            return
        restored = []
        for phase in phases:
            if (
                not isinstance(phase, (list, tuple)) or len(phase) != 2
                or not all(type(value) in (int, float) for value in phase)
                or not -MAX_RESTART_MARGIN <= phase[0] <= MAX_RESTART_MARGIN
                or not 0 <= phase[1] <= MAX_COLD_TAIL_SHARE
            ):
                return
            restored.append(tuple(phase))
        self.phases[:0] = restored
