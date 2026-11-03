"""Test-only client timeouts preserve production defaults and bounded failures."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import Mock

import custom_components.genesis_wp as integration
from custom_components.genesis_wp.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from . import harness
from .helpers import Unreachable, entry_data, setup_entry


# DHF-TEST: genesis-wp-ha/requirement-1 genesis-wp-ha/ac-63
async def test_suite_clients_use_test_timeout(hass, start_emulator, monkeypatch):
    emu = await start_emulator()
    original = integration.ThermiaGenesis
    clients = []

    def construct(*args, **kwargs):
        client = original(*args, **kwargs)
        clients.append(client)
        return client

    constructor = Mock(side_effect=construct)
    monkeypatch.setattr(integration, "ThermiaGenesis", constructor)
    await integration.read_capabilities(entry_data(emu))
    entry = await setup_entry(hass, emu)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    assert constructor.call_count >= 2
    assert harness.TEST_CLIENT_TIMEOUT == 15.0
    assert all(client._timeout == harness.TEST_CLIENT_TIMEOUT for client in clients)


# DHF-TEST: genesis-wp-ha/requirement-1 genesis-wp-ha/ac-63
def test_production_create_client_passes_no_timeout(monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(integration, "ThermiaGenesis", constructor)
    integration.create_client(entry_data(Unreachable()))
    assert "timeout" not in constructor.call_args.kwargs


# DHF-TEST: genesis-wp-ha/requirement-1 genesis-wp-ha/ac-64
async def test_silent_server_setup_fails_within_bound(hass, socket_enabled):
    writers = []
    accepted = asyncio.Event()

    def accept(reader, writer):
        writers.append(writer)
        accepted.set()

    server = await asyncio.start_server(accept, "127.0.0.1", 0)
    data = entry_data(Unreachable())
    data["port"] = server.sockets[0].getsockname()[1]
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    started = time.monotonic()
    setup = asyncio.create_task(hass.config_entries.async_setup(entry.entry_id))
    try:
        done, _ = await asyncio.wait({setup}, timeout=2 * harness.TEST_CLIENT_TIMEOUT)
        assert setup in done, "setup did not finish within 30 seconds"
        result = setup.result()
        assert accepted.is_set()
        assert result is False
        assert entry.state in (ConfigEntryState.SETUP_RETRY, ConfigEntryState.SETUP_ERROR)
        assert time.monotonic() - started < 2 * harness.TEST_CLIENT_TIMEOUT
    finally:
        server.close()
        for writer in writers:
            writer.close()
            await writer.wait_closed()
        await server.wait_closed()
        if not setup.done():
            setup.cancel()
        await asyncio.gather(setup, return_exceptions=True)
