"""The genesis_wp integration: read-only heat pumps on the Thermia Genesis platform."""
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CARD_URL
from .const import CONF_CAPABILITIES
from .const import CONF_MODE
from .const import CONF_MODEL
from .const import CONF_PROFILE
from .const import CONF_UNIT
from .const import CORE_SETTINGS
from .const import DOMAIN
from .const import EMULATOR_DYNAMICS_INTERVAL
from .const import EMULATOR_HOST
from .const import MODE_EMULATED

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


def capability_evidence(kind) -> list[str]:
    """Registers the library's capability rules read for ``kind``; always fetched (requirement-12)."""
    names = {n for rule in CAPABILITY_RULES for n in (rule.enable, *rule.sensors, *rule.signals) if n is not None}
    return sorted(n for n in names if REGISTERS[n][kind])


def capability_overrides(options) -> dict[str, str]:
    """The entry's module choices as library overrides; anything this library version rejects is dropped."""
    overrides = {}
    for name, state in options.items():
        if name in CAPABILITY_NAMES and state in (PRESENT, ABSENT):
            overrides[name] = state
        else:
            _LOGGER.warning("Ignoring module option %s=%s: not a capability state", name, state)
    return overrides


def create_client(data, overrides=None) -> ThermiaGenesis:
    """Build the library client for a config entry's data; always read-only."""
    return ThermiaGenesis(
        data[CONF_HOST],
        port=data[CONF_PORT],
        kind=data[CONF_MODEL],
        unit_id=data[CONF_UNIT],
        read_only=True,
        capability_overrides=overrides,
    )


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Serve the heating curve card and load it in every dashboard (requirement-11)."""
    if hass.http is not None:
        card = Path(__file__).parent / "frontend" / Path(CARD_URL).name
        await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(card), False)])
    if DATA_EXTRA_MODULE_URL in hass.data:  # absent when the frontend is not loaded
        add_extra_js_url(hass, CARD_URL)
    return True


async def detect_capabilities(profile: Profile, capabilities=None) -> dict[str, str]:
    """Capability states the library detects on ``profile`` served with the ``capabilities`` selection."""
    emulator = Emulator(profile, host=EMULATOR_HOST, port=0, capabilities=capabilities)
    await emulator.start()
    client = create_client(
        {CONF_HOST: emulator.host, CONF_PORT: emulator.port, CONF_MODEL: profile.model, CONF_UNIT: profile.unit_id}
    )
    try:
        await client.async_update(only_registers=capability_evidence(profile.model))
        return {name: cap.state for name, cap in client.capabilities.items()}
    finally:
        await client.close()
        await emulator.stop()


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
    coordinator = GenesisDataUpdateCoordinator(hass, entry, connection, emulator)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # The entities subscribed their registers while being added; read them now
    # instead of one update interval later.
    await coordinator.async_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_close()

    return unload_ok


class GenesisDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetches the registers the entities of one heat pump subscribed to."""

    def __init__(self, hass, entry: ConfigEntry, connection, emulator: Emulator | None = None):
        """Initialize; ``connection`` holds host, port and unit, ``emulator`` is set for an emulated entry."""
        self.thermia = create_client(connection, capability_overrides(entry.options))
        self.emulator = emulator
        self.kind = entry.data[CONF_MODEL]
        self.entry_id = entry.entry_id
        self.attributes = {}
        # Capability states the entities were created for, set after the first refresh (requirement-12).
        self.setup_capabilities: dict[str, str] | None = None
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
        self.evidence = capability_evidence(self.kind)
        self.registerAttribute(self.evidence)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.update_device_info()

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
            # The library's message names the host, which is topology: keep it out of the log.
            raise UpdateFailed(f"heat pump read failed ({type(error).__name__})") from None
        _LOGGER.debug(
            "Fetched %d registers in %.2f s", len(data), time.monotonic() - start_time
        )
        self._check_capabilities()
        return data

    def freeze_capabilities(self):
        """Fix the capability states the entities are created for; absent ones gate theirs out."""
        capabilities = self.thermia.capabilities
        self.setup_capabilities = {name: cap.state for name, cap in capabilities.items()}
        self.excluded = frozenset(r for cap in capabilities.values() if cap.state == ABSENT for r in cap.gates)
        for name, cap in capabilities.items():
            _LOGGER.debug("Capability %s: %s (%s)", name, cap.state, "; ".join(cap.evidence))

    def _check_capabilities(self):
        """Reload the entry once when a capability absent at setup is no longer absent.

        A capability turning absent at runtime keeps its entities until the next setup, so a
        seasonal switch such as passive cooling does not make entities come and go. An update
        that could not read all evidence registers is not taken as a change.
        """
        if self.setup_capabilities is None or self._reload_scheduled or self.thermia.unread & set(self.evidence):
            return
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
