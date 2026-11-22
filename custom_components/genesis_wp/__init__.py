"""The genesis_wp integration: read-only heat pumps on the Thermia Genesis platform."""
import asyncio
import logging
import time
from datetime import timedelta
from pathlib import Path

from genesis_wp import ThermiaException
from genesis_wp import ThermiaGenesis
from genesis_wp import const as genesis_const
from genesis_wp import register_category
from genesis_wp import register_role
from genesis_wp.capabilities import ABSENT
from genesis_wp.capabilities import CAPABILITY_NAMES
from genesis_wp.capabilities import CAPABILITY_RULES
from genesis_wp.capabilities import PRESENT
from genesis_wp.const import ATTR_INPUT_COMPRESSOR_SPEED_RPM
from genesis_wp.derived import BRINE
from genesis_wp.derived import CONDENSER
from genesis_wp.derived import FlowEstimate
from genesis_wp.derived import FlowEstimator
from genesis_wp.derived import HC2_BUFFER
from genesis_wp.derived import HC2_COMPRESSOR
from genesis_wp.derived import HC2_PASSIVE_COOLING
from genesis_wp.derived import HC2_PUMP
from genesis_wp.derived import HC2_SUPPLY
from genesis_wp.derived import HeatingCircuit2ReturnEstimator
from genesis_wp.derived import NO_RETURN
from genesis_wp.const import GENESIS_17_MODELS
from genesis_wp.const import KEY_ADDRESS
from genesis_wp.const import KEY_REG_TYPE
from genesis_wp.const import MODEL_NAMES
from genesis_wp.const import REGISTERS
from genesis_wp.emulator import Emulator
from genesis_wp.emulator import get_profile
from genesis_wp.emulator import Profile
from genesis_wp.groups import ROLE_MEASUREMENT
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.components.frontend import async_remove_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.const import EntityCategory
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CARD_URLS
from .const import CONF_CAPABILITIES
from .const import CONF_CAPABILITIES_SEEN
from .const import CONF_MODE
from .const import CONF_MODEL
from .const import CONF_PROFILE
from .const import CONF_UNIT
from .const import CORE_SETTINGS
from .const import DOMAIN
from .const import HC2_RETURN_DEFAULTS
from .const import EMULATOR_DYNAMICS_INTERVAL
from .const import EMULATOR_HOST
from .const import MODE_EMULATED

from .balance import DailyHeat
from .cycles import RunTracker

POWER_OUTPUT = genesis_const.ATTR_INPUT_CURRENT_POWER_OUTPUT
COMPRESSOR_SIGNAL = genesis_const.ATTR_DINPUT_COMPRESSOR_CONTROL_SIGNAL
OPERATING_MODE = genesis_const.ATTR_INPUT_FIRST_PRIORITISED_DEMAND

# Read-only: the write platforms (climate, number, switch) are not forwarded.
PLATFORMS = ["sensor", "binary_sensor"]

SCAN_INTERVAL = timedelta(seconds=30)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

VERSION_REGISTERS = {
    "control_software": (  # inputs 311-313
        genesis_const.ATTR_INPUT_CONTROL_SOFTWARE_VERSION_MAJOR,
        genesis_const.ATTR_INPUT_CONTROL_SOFTWARE_VERSION_MINOR,
        genesis_const.ATTR_INPUT_CONTROL_SOFTWARE_VERSION_MICRO,
    ),
    "software": (  # inputs 57-59
        genesis_const.ATTR_INPUT_SOFTWARE_VERSION_MAJOR,
        genesis_const.ATTR_INPUT_SOFTWARE_VERSION_MINOR,
        genesis_const.ATTR_INPUT_SOFTWARE_VERSION_MICRO,
    ),
}


def _rule_evidence(rule):
    return (rule.enable, *rule.sensors, *rule.signals, *rule.running)


def capability_evidence(kind) -> list[str]:
    """Registers the library's capability rules read for ``kind``; always fetched (requirement-12)."""
    names = {
        n
        for rule in CAPABILITY_RULES
        for n in _rule_evidence(rule)
        if n is not None
    }
    return sorted(n for n in names if REGISTERS[n][kind])


def capability_overrides(options) -> dict[str, str]:
    """The entry's module choices as library overrides; anything this library version rejects is dropped."""
    overrides = {}
    for name, state in options.items():
        if name in HC2_RETURN_DEFAULTS:
            continue
        if name in CAPABILITY_NAMES and state in (PRESENT, ABSENT):
            overrides[name] = state
        else:
            _LOGGER.warning("Ignoring module option %s=%s: not a capability state", name, state)
    return overrides


def create_client(data, overrides=None, seen=None) -> ThermiaGenesis:
    """Build the library client for a config entry's data; always read-only."""
    return ThermiaGenesis(
        data[CONF_HOST],
        port=data[CONF_PORT],
        kind=data[CONF_MODEL],
        unit_id=data[CONF_UNIT],
        read_only=True,
        capability_overrides=overrides,
        capabilities_seen=seen,
    )


def create_entry_client(entry: ConfigEntry, connection) -> ThermiaGenesis:
    """The entry's client, seeded with the modules seen running before (issue-8).

    A stored name this library version rejects drops the whole seed with a warning: detection
    starts over rather than failing setup.
    """
    overrides = capability_overrides(entry.options)
    seen = entry.data.get(CONF_CAPABILITIES_SEEN) or None
    try:
        return create_client(connection, overrides, seen)
    except ValueError as error:
        _LOGGER.warning("Ignoring stored capabilities seen running: %s", error)
        return create_client(connection, overrides)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Serve and register the read-only dashboard cards (requirements 11 and 18)."""
    # DHF-REQ: genesis-wp-ha/requirement-18
    if hass.http is not None:
        await hass.http.async_register_static_paths([
            StaticPathConfig(url, str(Path(__file__).parent / "frontend" / Path(url).name), False)
            for url in (*CARD_URLS, "/genesis_wp/register-card.js", "/genesis_wp/patch.js", "/genesis_wp/labels.js",
                        "/genesis_wp/genesis-wp-panel.js")
        ])
    if DATA_EXTRA_MODULE_URL in hass.data:
        for url in CARD_URLS:
            add_extra_js_url(hass, url)
    return True


async def detect_capabilities(profile: Profile, capabilities=None) -> dict[str, str]:
    """Capability states the library detects on ``profile`` served with the ``capabilities`` selection."""
    emulator = Emulator(profile, host=EMULATOR_HOST, port=0, capabilities=capabilities)
    await emulator.start()
    try:
        return await read_capabilities(
            {CONF_HOST: emulator.host, CONF_PORT: emulator.port, CONF_MODEL: profile.model, CONF_UNIT: profile.unit_id}
        )
    finally:
        await emulator.stop()


async def read_capabilities(data) -> dict[str, str]:
    """Capability states the library detects on the heat pump of ``data``; reads only (requirement-16)."""
    client = create_client(data)
    try:
        await client.async_update(only_registers=capability_evidence(data[CONF_MODEL]))
        if client.unread & set(capability_evidence(data[CONF_MODEL])):
            raise ThermiaException("capability evidence not read")
        return {name: cap.state for name, cap in client.capabilities.items()}
    finally:
        await client.close()


async def _start_emulator(entry: ConfigEntry) -> Emulator:
    """Run the entry's firmware profile, with its module selection, in-process on a free loopback port."""
    try:
        emulator = Emulator(
            get_profile(entry.data[CONF_PROFILE]),
            host=EMULATOR_HOST,
            port=0,
            dynamics=True,
            dynamics_interval=EMULATOR_DYNAMICS_INTERVAL,
            capabilities=entry.data.get(CONF_CAPABILITIES) or None,
        )
    except ValueError as error:  # CapabilityError: a selection this library version cannot present
        raise ConfigEntryNotReady(f"emulator profile rejected: {error}") from None
    try:
        await emulator.start()
    except OSError as error:
        raise ConfigEntryNotReady(f"emulator did not start ({type(error).__name__})") from None
    return emulator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a heat pump from a config entry: a real one by host, or an emulated one in-process."""
    emulator = None
    connection = entry.data
    if entry.data.get(CONF_MODE) == MODE_EMULATED:
        emulator = await _start_emulator(entry)
        connection = {
            **entry.data,
            CONF_HOST: emulator.host,
            CONF_PORT: emulator.port,
            CONF_UNIT: emulator.profile.unit_id,
        }
    store = flow_calibration_store(hass, entry.entry_id)
    calibrations = await store.async_load() or {}
    coordinator = GenesisDataUpdateCoordinator(hass, entry, connection, emulator, store, calibrations)
    await coordinator.async_restore_runs()
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        # The abandoned coordinator leaves no pending statistics write; a retry reuses the store.
        coordinator.discard_pending_runs()
        await coordinator.async_close()
        raise ConfigEntryNotReady

    coordinator.update_device_info()
    # Register the heat pump first: the category sub-devices are its children (requirement-15).
    coordinator.device_id = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **coordinator.device_info
    ).id
    coordinator.freeze_capabilities()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # DHF-REQ: genesis-wp-ha/requirement-21
    if "genesis-wp" not in hass.data.get("frontend_panels", {}):
        await async_register_panel(
            hass, webcomponent_name="genesis-wp-panel", frontend_url_path="genesis-wp",
            sidebar_title="Heat pump", sidebar_icon="mdi:heat-pump",
            module_url="/genesis_wp/genesis-wp-panel.js", require_admin=False,
        )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if all(platform in coordinator.setup_entity_ids for platform in PLATFORMS):
        _remove_stale_entities(hass, entry, coordinator)
        _remove_empty_child_devices(hass, entry.entry_id, coordinator.device_id)
    # The entities subscribed their registers while being added; read them now
    # instead of one update interval later.
    await coordinator.async_refresh()

    return True


# DHF-REQ: genesis-wp-ha/requirement-14
def _remove_stale_entities(hass, entry, coordinator):
    """Remove registry entries the configured platforms no longer provide."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            entity.unique_id not in coordinator.setup_entity_ids.get(entity.domain, ())
            and entity.unique_id not in coordinator.setup_retained_entity_ids
        ):
            registry.async_remove(entity.entity_id)
            _LOGGER.info("Removed stale entity with unique ID %s", entity.unique_id)


# DHF-REQ: genesis-wp-ha/requirement-15
def _remove_empty_child_devices(hass, entry_id, parent_device_id):
    """Remove this entry's category devices once they have no registry entities."""
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    for child in dr.async_entries_for_parent_device(devices, parent_device_id):
        if child.config_entry_id != entry_id:
            continue
        if er.async_entries_for_device(entities, child.id, include_disabled_entities=True):
            continue
        devices.async_remove_device(child.id)
        _LOGGER.info("Removed empty child device with registry ID %s", child.id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_save_calibrations()
        await coordinator.async_save_runs()
        hass.data.get(DATA_RUN_STORES, {}).pop(entry.entry_id, None)
        await coordinator.async_close()
        if not hass.data[DOMAIN]:
            async_remove_panel(hass, "genesis-wp")

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Discard observations and calibration owned by the removed entry."""
    # DHF-REQ: genesis-wp-ha/requirement-26  (ac-111)
    await flow_calibration_store(hass, entry.entry_id).async_remove()
    # The shared instance, when a retrying setup or a failed unload left one, cancels its pending write.
    await compressor_run_store(hass, entry.entry_id).async_remove()
    hass.data[DATA_RUN_STORES].pop(entry.entry_id, None)


# DHF-REQ: genesis-wp-ha/requirement-26
# The learned pump-speed calibration per loop, kept across restarts (ac-110).
FLOW_CALIBRATION_VERSION = 1
FLOW_CALIBRATION_SAVE_DELAY = 300  # [s]


def flow_calibration_store(hass: HomeAssistant, entry_id: str) -> Store:
    """The entry's stored calibrations, ``{loop key: L/min per %}``."""
    return Store(hass, FLOW_CALIBRATION_VERSION, f"{DOMAIN}.flow_calibration.{entry_id}")


COMPRESSOR_RUN_SAVE_DELAY = 30  # [s]
DATA_RUN_STORES = f"{DOMAIN}_compressor_run_stores"


# DHF-REQ: genesis-wp-ha/requirement-28
class CompressorRunStore:
    """The single owner of one entry's stored daily compressor observations.

    Every coordinator of the entry (setup retries included) and its removal share this
    instance, so a pending write is always cancellable. It owns its debounce timer and
    final-write listener instead of Store.async_delay_save, whose callbacks only the
    arming Store instance can cancel. Once closed or removed it writes nothing
    (ac-161, ac-165, ac-166).
    """

    def __init__(self, hass: HomeAssistant, entry_id: str):
        self._hass = hass
        self._store = Store(hass, 1, f"{DOMAIN}.compressor_runs.{entry_id}")
        self._data_func = None
        self._unsub_timer = None
        self._unsub_final_write = None
        self.closed = False
        # Serializes writes with deletion: removal waits for a write already in flight (ac-166).
        self._lock = asyncio.Lock()

    async def async_load(self):
        return await self._store.async_load()

    @callback
    def async_delay_save(self, data_func) -> None:
        """Write ``data_func()`` after the delay; armed once while a write is pending (issue-24)."""
        if self.closed:
            return
        self._data_func = data_func
        if self._unsub_timer is None:
            self._unsub_timer = async_call_later(self._hass, COMPRESSOR_RUN_SAVE_DELAY, self._async_timer)
        if self._unsub_final_write is None:
            self._unsub_final_write = self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_FINAL_WRITE, self._async_final_write
            )

    async def _async_timer(self, _now) -> None:
        self._unsub_timer = None
        await self._async_write()

    async def _async_final_write(self, _event) -> None:
        self._unsub_final_write = None
        await self._async_write()

    async def _async_write(self) -> None:
        async with self._lock:
            if self.closed or self._data_func is None:
                return
            data, self._data_func = self._data_func(), None
            await self._store.async_save(data)

    @callback
    def async_cancel(self) -> None:
        """Drop a pending write; the store stays open."""
        self._data_func = None
        for unsub in (self._unsub_timer, self._unsub_final_write):
            if unsub is not None:
                unsub()
        self._unsub_timer = self._unsub_final_write = None

    async def async_close(self, data) -> None:
        """Write ``data`` (when given) now and accept no later writes."""
        if self.closed:
            return
        # Closed before the first await, so a refresh during the flush cannot re-arm a write.
        self.closed = True
        self.async_cancel()
        if data is not None:
            async with self._lock:
                await self._store.async_save(data)

    async def async_remove(self) -> None:
        """Cancel pending writes, accept no later ones, and delete the stored observations."""
        self.closed = True
        self.async_cancel()
        async with self._lock:
            await self._store.async_remove()


def compressor_run_store(hass: HomeAssistant, entry_id: str) -> CompressorRunStore:
    """The entry's run store, shared until the entry unloads or is removed."""
    stores = hass.data.setdefault(DATA_RUN_STORES, {})
    if entry_id not in stores:
        stores[entry_id] = CompressorRunStore(hass, entry_id)
    return stores[entry_id]


def seeded_estimator(key: str, loop, seed) -> FlowEstimator:
    """A loop's estimator from a stored calibration; one the library rejects is dropped."""
    if seed is None:
        return FlowEstimator(loop)
    try:
        estimator = FlowEstimator(loop, calibration=seed)
    except ValueError as error:
        _LOGGER.warning("%s: stored flow calibration dropped (%s)", key, error)
        return FlowEstimator(loop)
    _LOGGER.debug("%s: flow estimator seeded with calibration %s L/min per %%", key, seed)
    return estimator


# Derived flow sensors by entity key; the library's derived module owns the estimate.
FLOW_LOOPS = {"condenser_flow": CONDENSER, "brine_flow": BRINE}


def flow_registers(loop) -> list[str]:
    """The registers a loop's flow estimator reads."""
    return [r for r in (loop.heat_in, loop.heat_out, loop.warm, loop.cold, loop.pump,
                        ATTR_INPUT_COMPRESSOR_SPEED_RPM) if r]


class GenesisDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetches the registers the entities of one heat pump subscribed to."""

    def __init__(self, hass, entry: ConfigEntry, connection, emulator: Emulator | None = None,
                 store: Store | None = None, calibrations: dict | None = None):
        """Initialize; ``connection`` holds host, port and unit, ``emulator`` is set for an emulated entry.

        ``store`` keeps the flow calibrations across restarts, ``calibrations`` is its loaded content.
        """
        self.thermia = create_entry_client(entry, connection)
        self.emulator = emulator
        self.kind = entry.data[CONF_MODEL]
        self.entry_id = entry.entry_id
        self.attributes = {}
        self.setup_entity_ids: dict[str, set[str]] = {}
        # Capability states the entities were created for, set after the first refresh (requirement-12).
        self.setup_capabilities: dict[str, str] | None = None
        self.setup_retained_entity_ids: set[str] = set()
        self.excluded: frozenset[str] = frozenset()
        self._reload_scheduled = False
        # Device registry ID of the heat pump, the parent of the category devices; set during setup.
        self.device_id: str | None = None
        # Controller software and Genesis platform version identify the firmware profile.
        if self.kind in GENESIS_17_MODELS:
            self.sw_version_registers = VERSION_REGISTERS["control_software"]
            self.hw_version_registers = VERSION_REGISTERS["software"]
        else:
            self.sw_version_registers = VERSION_REGISTERS["software"]
            self.hw_version_registers = ()
        self.registerAttribute(
            [r for r in (*self.sw_version_registers, *self.hw_version_registers) if REGISTERS[r][self.kind]]
        )
        self.run_tracker = None
        self._run_store = None
        if all(REGISTERS[register][self.kind] for register in (COMPRESSOR_SIGNAL, OPERATING_MODE)):
            self.run_tracker = RunTracker()
            self._run_store = compressor_run_store(hass, entry.entry_id)
            self.registerAttribute([COMPRESSOR_SIGNAL, OPERATING_MODE])
        self.evidence = capability_evidence(self.kind)
        self.registerAttribute(self.evidence)
        # DHF-REQ: genesis-wp-ha/requirement-26
        # One flow estimator per loop for the entry's lifetime: it learns its pump-speed
        # calibration across windows. Only loops whose registers this model has get one.
        self.flow_clock = time.monotonic
        calibrations = calibrations if isinstance(calibrations, dict) else {}
        self.flow_estimators = {
            key: seeded_estimator(key, loop, calibrations.get(key)) for key, loop in FLOW_LOOPS.items()
            if all(REGISTERS[r][self.kind] for r in flow_registers(loop))
        }
        self.flow_store = store
        self._saved_calibrations = self.calibrations()
        # Home Assistant's delayed save is a debounce: re-arming it on every poll would postpone
        # the write indefinitely (issue-24), so it is armed once and cleared when it writes.
        self._save_pending = False
        self.flows: dict[str, FlowEstimate] = {}
        # Read the estimators' inputs every update, whether or not their own entities are enabled.
        self.registerAttribute(sorted({r for e in self.flow_estimators.values() for r in flow_registers(e.loop)}))

        self.hc2_return = NO_RETURN
        self.hc2_estimator = None
        self.circuit_flow = entry.options.get("circuit_flow", HC2_RETURN_DEFAULTS["circuit_flow"])
        buffer_volume = entry.options.get("buffer_volume", HC2_RETURN_DEFAULTS["buffer_volume"])
        hc2_registers = [*HC2_BUFFER, HC2_SUPPLY, HC2_COMPRESSOR, HC2_PUMP, *HC2_PASSIVE_COOLING]
        self.supports_hc2_return = (
            "condenser_flow" in self.flow_estimators and all(REGISTERS[r][self.kind] for r in hc2_registers)
        )
        self.produced_heat = DailyHeat() if REGISTERS[POWER_OUTPUT][self.kind] else None
        if self.produced_heat is not None:
            self.registerAttribute(POWER_OUTPUT)
        if self.supports_hc2_return and buffer_volume is not None and self.circuit_flow is not None:
            try:
                self.hc2_estimator = HeatingCircuit2ReturnEstimator(buffer_volume, self.circuit_flow)
            except ValueError:
                _LOGGER.warning("Invalid heating circuit 2 return estimation options")
            else:
                self.registerAttribute(hc2_registers)
        # DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-178
        # Room heat exists only where an estimator can supply it.
        self.rooms_heat = DailyHeat() if self.hc2_estimator is not None else None
        if self.rooms_heat is not None:
            self.registerAttribute([HC2_PUMP, OPERATING_MODE])

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.update_device_info()

    def calibrations(self) -> dict[str, float]:
        """The learned calibration per loop; loops without one are left out."""
        return {k: e.calibration for k, e in self.flow_estimators.items() if e.calibration is not None}

    async def async_save_calibrations(self):
        """Write the calibrations now if they changed since the last save."""
        current = self.calibrations()
        if self.flow_store is None or current == self._saved_calibrations:
            return
        await self.flow_store.async_save(current)
        self._saved_calibrations = current
        self._save_pending = False

    async def async_restore_runs(self):
        """Restore the current local day's snapshot before the first refresh."""
        if self._run_store is None:
            return
        try:
            snapshot = await self._run_store.async_load()
        except Exception as error:  # noqa: BLE001 - a bad snapshot must not block setup (ac-162)
            _LOGGER.warning("Compressor statistics snapshot unreadable, starting empty (%s)",
                            type(error).__name__)
            return
        self.run_tracker.restore(dt_util.now(), snapshot)

    async def async_save_runs(self):
        """Flush compressor observations when the entry unloads; later updates schedule no writes."""
        if self._run_store is not None:
            daily = self.run_tracker.daily
            await self._run_store.async_close(daily.as_dict() if daily is not None else None)

    @callback
    def discard_pending_runs(self):
        """Drop a pending statistics write and keep the store open."""
        if self._run_store is not None:
            self._run_store.async_cancel()

    def _track_run(self, signal, mode=None):
        if self.run_tracker is not None and self.run_tracker.add(dt_util.now(), signal, mode):
            self._run_store.async_delay_save(self.run_tracker.daily.as_dict)

    async def async_close(self):
        """Close the client, then stop the entry's emulator if it has one."""
        await self.thermia.close()
        if self.emulator is not None:
            await self.emulator.stop()

    async def _async_update_data(self):
        """Update data via library."""
        start_time = time.monotonic()
        try:
            data = await self.thermia.async_update(only_registers=self.attributes.keys())
        except ThermiaException as error:
            self._track_run(None)
            if self.hc2_estimator is not None:
                self.hc2_return = self.hc2_estimator.add(self.flow_clock(), {}, None)
            self._track_heat(None, None, False)
            # The library's message names the host, which is topology: keep it out of the log.
            raise UpdateFailed(f"heat pump read failed ({type(error).__name__})") from None
        _LOGGER.debug(
            "Fetched %d registers in %.2f s", len(data), time.monotonic() - start_time
        )
        self._check_capabilities()
        self._store_seen()
        self._estimate_flows(data)
        unread = self.thermia.unread
        # DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-174
        # Hot-water hours count as FR2 time but are never covered (requirement-29).
        hot_water = OPERATING_MODE not in unread and data.get(OPERATING_MODE) == "Hot water"
        self._track_heat(
            None if POWER_OUTPUT in unread else data.get(POWER_OUTPUT),
            None if hot_water else self.hc2_return.heat,
            HC2_PUMP not in unread and data.get(HC2_PUMP) is True,
        )
        if self.run_tracker is not None:
            signal = None if COMPRESSOR_SIGNAL in unread else data.get(COMPRESSOR_SIGNAL)
            mode = None if OPERATING_MODE in unread else data.get(OPERATING_MODE)
            self._track_run(signal, mode)
        return data

    def _track_heat(self, power, heat, pump_on):
        """Accumulate heat once per coordinator refresh."""
        now = dt_util.now()
        if self.produced_heat is not None:
            self.produced_heat.add(now, power)
        if self.rooms_heat is not None:
            self.rooms_heat.add(now, heat, pump_on)

    @property
    def rooms_heat_estimable(self) -> bool:
        """False once heating circuit 2 or its buffer tank is confirmed absent."""
        return self.hc2_estimator is not None and not any(
            self.thermia.capability_state(name) == ABSENT for name in ("buffer_tank", "heating_circuit_2")
        )

    def _estimate_flows(self, data):
        """Feed each loop's estimator; registers not read this update count as missing, never as 0."""
        if not self.flow_estimators:
            return
        now = self.flow_clock()
        unread = self.thermia.unread
        read = {r: v for r, v in data.items() if r not in unread}
        for key, estimator in self.flow_estimators.items():
            estimate = estimator.add(now, read)
            self.flows[key] = estimate
            _LOGGER.debug("%s: %s L/min (%s, calibration %s L/min per %%)", key, estimate.value,
                          estimate.source, estimate.calibration)
        # DHF-REQ: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-118
        if self.hc2_estimator is not None:
            if not self.rooms_heat_estimable:
                self.hc2_estimator.add(now, {}, None)
                self.hc2_return = NO_RETURN
            else:
                self.hc2_return = self.hc2_estimator.add(now, read, self.flows["condenser_flow"].value)
        current = self.calibrations()
        if self.flow_store is not None and not self._save_pending and current != self._saved_calibrations:
            self._save_pending = True
            self.flow_store.async_delay_save(self._mark_saved, FLOW_CALIBRATION_SAVE_DELAY)

    def _mark_saved(self) -> dict[str, float]:
        """The delayed save's payload: the calibrations at write time."""
        self._saved_calibrations = self.calibrations()
        self._save_pending = False
        return self._saved_calibrations

    def freeze_capabilities(self):
        """Fix the capability states the entities are created for; absent ones gate theirs out."""
        capabilities = self.thermia.capabilities
        self.setup_capabilities = {name: cap.state for name, cap in capabilities.items()}
        self.excluded = frozenset(r for cap in capabilities.values() if cap.state == ABSENT for r in cap.gates)
        self.setup_retained_entity_ids = self._uncertain_entity_ids(capabilities)
        for name, cap in capabilities.items():
            _LOGGER.debug("Capability %s: %s (%s)", name, cap.state, "; ".join(cap.evidence))

    # DHF-REQ: genesis-wp-ha/requirement-12
    def _uncertain_entity_ids(self, capabilities) -> set[str]:
        """Keep registry entries gated out solely by incomplete automatic evidence."""
        unread = self.thermia.unread
        if not unread:
            return set()

        uncertain = set()
        confirmed_exclusions = set()
        # The library orders rules so member capabilities precede combined rules.
        for rule in CAPABILITY_RULES:
            capability = capabilities.get(rule.name)
            if capability is None or capability.state != ABSENT:
                continue
            if not capability.overridden and (
                unread.intersection(_rule_evidence(rule))
                or uncertain.intersection(rule.members)
            ):
                uncertain.add(rule.name)
                _LOGGER.info("Deferring registry cleanup for %s due to unread evidence", rule.name)
            else:
                confirmed_exclusions.update(capability.gates)

        uncertain_exclusions = {register for name in uncertain for register in capabilities[name].gates}
        return {self.unique_id(register) for register in uncertain_exclusions - confirmed_exclusions}

    def _store_seen(self):
        """Keep the modules the library has seen running in the entry, so a reload still counts them."""
        seen = sorted(self.thermia.capabilities_seen)
        if seen != (self.config_entry.data.get(CONF_CAPABILITIES_SEEN) or []):
            _LOGGER.info("Capabilities seen running: %s", ", ".join(seen))
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, CONF_CAPABILITIES_SEEN: seen}
            )

    def _check_capabilities(self):
        """Reload the entry once when a capability absent at setup is no longer absent.

        A capability turning absent at runtime keeps its entities until the next setup, so a
        seasonal switch such as passive cooling does not make entities come and go. An update
        that could not read all evidence registers is not taken as a change.
        """
        if self.setup_capabilities is None or self._reload_scheduled or self.thermia.unread & set(self.evidence):
            return
        self._resolve_retained_entities()
        appeared = sorted(
            name
            for name, cap in self.thermia.capabilities.items()
            if cap.state != ABSENT and self.setup_capabilities.get(name) == ABSENT
        )
        if appeared:
            for name in appeared:
                _LOGGER.info("Capability %s changed from absent to %s; reloading to add its entities",
                             name, self.thermia.capabilities[name].state)
            self._reload_scheduled = True
            self.hass.config_entries.async_schedule_reload(self.entry_id)

    # DHF-REQ: genesis-wp-ha/requirement-12
    def _resolve_retained_entities(self):
        """Finish the cleanup deferred at setup once a complete read confirms the capability absent.

        Called only after an update that read every evidence register. Entries whose capability
        is no longer absent stay; the absent-to-present reload adds their entities.
        """
        if not self.setup_retained_entity_ids:
            return
        confirmed = {
            self.unique_id(register)
            for cap in self.thermia.capabilities.values()
            if cap.state == ABSENT
            for register in cap.gates
        }
        removable = self.setup_retained_entity_ids & confirmed
        if not removable:
            return
        registry = er.async_get(self.hass)
        for entity in er.async_entries_for_config_entry(registry, self.entry_id):
            if entity.unique_id in removable:
                registry.async_remove(entity.entity_id)
                _LOGGER.info("Removed entity with unique ID %s: absence confirmed by a complete read",
                             entity.unique_id)
        self.setup_retained_entity_ids = self.setup_retained_entity_ids - removable
        if self.device_id is not None:
            _remove_empty_child_devices(self.hass, self.entry_id, self.device_id)

    def has_value(self, register) -> bool:
        """True when the last update read this register and it is fitted (not None)."""
        return (
            self.data is not None
            and self.data.get(register) is not None
            and register not in self.thermia.unread
        )

    def unique_id(self, register) -> str:
        """Registry key of a register entity: entry ID plus the firmware's register type and address.

        Never the library's attribute name, which may be renamed, nor host or port, which change.
        """
        spec = REGISTERS[register]
        return f"{self.entry_id}_{spec[KEY_REG_TYPE]}_{spec[KEY_ADDRESS]}"

    def _version(self, registers):
        if not registers or not all(self.has_value(r) for r in registers):
            return None
        return ".".join(str(int(self.data[r])) for r in registers)

    def update_device_info(self):
        """Describe the device; versions come from the last update."""
        model = MODEL_NAMES[self.kind]
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.entry_id)},
            name=model if self.emulator is None else f"{model} (emulated)",
            manufacturer=model.split(" ", 1)[0],
            model=model,
            sw_version=self._version(self.sw_version_registers),
            hw_version=self._version(self.hw_version_registers),
        )

    def device_info_for(self, register) -> ChildDeviceInfo:
        """The child device of the register's category under the heat pump (requirement-15)."""
        category = register_category(register)
        return ChildDeviceInfo(
            identifiers={(DOMAIN, f"{self.entry_id}_{category}")},
            parent_device_id=self.device_id,
            translation_key=category,
        )

    @staticmethod
    def entity_category_for(register) -> EntityCategory | None:
        """Alarms and read-only settings are diagnostic; measurements and core set temperatures primary."""
        if register in CORE_SETTINGS or register_role(register) == ROLE_MEASUREMENT:
            return None
        return EntityCategory.DIAGNOSTIC

    def registerAttribute(self, attribute):
        if type(attribute) is list:
            for name in attribute:
                _LOGGER.debug("Register attribute for update: %s", name)
                self.attributes[name] = True
        else:
            _LOGGER.debug("Register attribute for update: %s", attribute)
            self.attributes[attribute] = True
