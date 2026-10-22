"""Shared test harness: the genesis-wp-emulator firmware profiles the suite runs against.

Device state comes only from the emulator's packaged profiles (requirement-1); the
profiles belong to the genesis-wp library and are never copied or edited here.
"""

from __future__ import annotations

PROFILE_606 = "stiebel-wpe-i-07.1-plus-6.0.6"  # software 6.0.6 / Genesis 17.2.40
PROFILE_615 = "stiebel-wpe-i-07.1-plus-6.1.5"  # software 6.1.5 / Genesis 17.3.145
PROFILES = (PROFILE_606, PROFILE_615)
FIRMWARE = {PROFILE_606: "6.0.6", PROFILE_615: "6.1.5"}
UNIT = 1
WPE_I_KIND = "stiebel_wpe_i_07_1"
