"""Shared test harness: the genesis-wp-emulator firmware profiles the suite runs against.

Device state comes only from the emulator's packaged profiles (requirement-1); the
profiles belong to the genesis-wp library and are never copied or edited here.
"""

from __future__ import annotations

from genesis_wp.capabilities import CAPABILITY_RULES
from genesis_wp.capabilities import gated_registers

PROFILE_606 = "stiebel-wpe-i-07.1-plus-6.0.6"  # software 6.0.6 / Genesis 17.2.40
PROFILE_615 = "stiebel-wpe-i-07.1-plus-6.1.5"  # software 6.1.5 / Genesis 17.3.145
PROFILES = (PROFILE_606, PROFILE_615)
FIRMWARE = {PROFILE_606: "6.0.6", PROFILE_615: "6.1.5"}
# DHF-REQ: genesis-wp-ha/requirement-1
TEST_CLIENT_TIMEOUT = 15.0
UNIT = 1
WPE_I_KIND = "stiebel_wpe_i_07_1"


DERIVED_SENSOR_KEYS = (
    "condenser_flow",
    "brine_flow",
    "hc2_return",
    "heat_to_rooms",
    "heat_produced_today",
    "heat_to_rooms_today",
    "starts_today",
    "hot_water_starts_today",
    "short_heating_runs_today",
    "running_hours_today",
    "heating_run_minimum",
    "heating_run_mean",
    "heating_run_maximum",
    "last_run_length",
)

# Capabilities the library detects as absent on the 6.1.5 capture, the owner's plant (requirement-12).
# Hot gas recovery reads input 45 = not fitted since genesis-wp 41d57be (change_request-52).
ABSENT_615 = ("hot_water", "pool", "active_cooling", "room_sensor", "electric_meter", "hot_gas_recovery")
_RULES = {rule.name: rule for rule in CAPABILITY_RULES}


def gates(*names) -> set[str]:
    """Registers the named capabilities gate on the WPE-I."""
    return {r for name in names for r in gated_registers(_RULES[name], WPE_I_KIND)}
