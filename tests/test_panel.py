"""Sidebar panel lifecycle on the loopback emulator."""
from pathlib import Path
from urllib.parse import urljoin

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component
from .helpers import setup_entry
from .harness import PROFILE_615
from .node_harness import run_node_harness

FRONTEND = Path(__file__).parent.parent / "custom_components" / "genesis_wp" / "frontend"


# DHF-TEST: genesis-wp-ha/requirement-35 genesis-wp-ha/ac-185
@pytest.mark.parametrize("version", ["1.2.3", "1.2.4"])
async def test_frontend_urls_use_manifest_version(
    hass, hass_client, start_emulator, monkeypatch, version
):
    assert await async_setup_component(hass, "http", {})
    hass.data[DATA_EXTRA_MODULE_URL] = UrlManager(lambda *_: None, [])
    integration = await async_get_integration(hass, "genesis_wp")
    monkeypatch.setitem(integration.manifest, "version", version)
    await setup_entry(hass, await start_emulator(PROFILE_615))

    prefix = f"/genesis_wp/{version}/"
    panel = hass.data["frontend_panels"]["genesis-wp"]
    panel_url = panel.config["_panel_custom"]["module_url"]
    assert panel_url == prefix + "genesis-wp-panel.js"
    assert set(hass.data[DATA_EXTRA_MODULE_URL].urls) == {
        prefix + "genesis-wp-device-card.js",
        prefix + "genesis-wp-heating-curve-card.js",
    }

    client = await hass_client()
    for module in FRONTEND.glob("*.js"):
        for url in (urljoin(panel_url, f"./{module.name}"), f"/genesis_wp/{module.name}"):
            response = await client.get(url)
            assert response.status == 200, url
            assert await response.read() == module.read_bytes(), url

    # A tab opened before an update still holds an earlier version's panel URL: it gets the
    # current entry, whose view import fails, so the reload message shows.
    retired = "/genesis_wp/1.2.2/"
    response = await client.get(retired + "genesis-wp-panel.js")
    assert response.status == 200
    assert await response.read() == (FRONTEND / "genesis-wp-panel.js").read_bytes()
    for module in FRONTEND.glob("*.js"):
        if module.name != "genesis-wp-panel.js":
            assert (await client.get(retired + module.name)).status == 404, module.name


# DHF-TEST: genesis-wp-ha/requirement-35 genesis-wp-ha/ac-184
@pytest.mark.parametrize(
    "failure", ["rejected_import", "missing_export", "missing_view_export", "retired_version"]
)
def test_panel_module_failure_shows_reload_message(tmp_path, failure):
    for module in FRONTEND.glob("*.js"):
        (tmp_path / module.name).write_bytes(module.read_bytes())
    card = tmp_path / "genesis-wp-device-card.js"
    if failure == "rejected_import":
        card.unlink()
    elif failure == "missing_export":
        card.write_text(
            "export class GenesisWpDeviceCard {}\n"
            "export const temperatureColor = () => '';\n"
            "export const toCelsius = (value) => value;\n",
            encoding="utf-8",
        )
    elif failure == "missing_view_export":
        (tmp_path / "genesis-wp-panel-view.js").write_text(
            "export {};\n", encoding="utf-8"
        )
    else:
        # A retired version's directory serves only the entry; its view import fails.
        for module in tmp_path.glob("*.js"):
            if module.name != "genesis-wp-panel.js":
                module.unlink()

    run_node_harness(
        Path(__file__).parent / "frontend" / "panel_failure.mjs",
        tmp_path / "genesis-wp-panel.js",
    )


# DHF-TEST: genesis-wp-ha/requirement-21 genesis-wp-ha/ac-81
async def test_panel_lifecycle(hass, hass_client, start_emulator):
    assert await async_setup_component(hass, "http", {})
    first = await setup_entry(hass, await start_emulator(PROFILE_615))
    panel = hass.data["frontend_panels"]["genesis-wp"]
    assert panel.sidebar_title == "Heat pump"
    assert panel.sidebar_icon == "mdi:heat-pump"
    assert not panel.require_admin
    url = panel.config["_panel_custom"]["module_url"]
    response = await (await hass_client()).get(url)
    assert response.status == 200
    assert await response.read() == Path("custom_components/genesis_wp/frontend/genesis-wp-panel.js").read_bytes()
    # Every module the panel imports is served next to it.
    frontend = Path("custom_components/genesis_wp/frontend")
    for name in ("patch.js", "labels.js", "genesis-wp-device-card.js", "genesis-wp-heating-curve-card.js", "register-card.js"):
        module = await (await hass_client()).get(url.rsplit("/", 1)[0] + "/" + name)
        assert module.status == 200, name
        assert await module.read() == (frontend / name).read_bytes(), name
    second = await setup_entry(hass, await start_emulator(PROFILE_615))
    assert await hass.config_entries.async_unload(first.entry_id)
    assert "genesis-wp" in hass.data["frontend_panels"]
    assert await hass.config_entries.async_unload(second.entry_id)
    assert "genesis-wp" not in hass.data["frontend_panels"]
