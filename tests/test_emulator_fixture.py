"""The emulator fixture serves every firmware profile to the genesis-wp client (requirement-1)."""

from __future__ import annotations

import pytest
from genesis_wp import ThermiaGenesis

from .harness import FIRMWARE
from .harness import PROFILES
from .harness import UNIT


@pytest.mark.parametrize("profile", PROFILES)
async def test_emulator_answers_a_full_read_only_update(start_emulator, profile):
    emu = await start_emulator(profile)
    client = ThermiaGenesis(emu.host, port=emu.port, kind=emu.profile.model, unit_id=UNIT)
    try:
        data = await client.async_update()
    finally:
        await client.close()

    assert client.read_only
    assert data
    assert client.firmware == FIRMWARE[profile]
    assert emu.writes == []
