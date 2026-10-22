"""The genesis_wp integration: read-only heat pumps on the Thermia Genesis platform."""
import logging
import time
from datetime import timedelta

from genesis_wp import ThermiaException
from genesis_wp import ThermiaGenesis
from genesis_wp.const import MODEL_NAMES
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import ATTR_MANUFACTURER
from .const import CONF_MODEL
from .const import CONF_UNIT
from .const import DOMAIN

# Read-only: the write platforms (climate, number, switch) are not forwarded.
PLATFORMS = ["sensor", "binary_sensor"]

SCAN_INTERVAL = timedelta(seconds=30)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


def create_client(data) -> ThermiaGenesis:
    """Build the library client for a config entry's data; always read-only."""
    return ThermiaGenesis(
        data[CONF_HOST],
        port=data[CONF_PORT],
        kind=data[CONF_MODEL],
        unit_id=data[CONF_UNIT],
        read_only=True,
    )


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the genesis_wp component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a heat pump from a config entry."""
    coordinator = GenesisDataUpdateCoordinator(hass, entry)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        await coordinator.thermia.close()
        raise ConfigEntryNotReady

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
        await coordinator.thermia.close()

    return unload_ok


class GenesisDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetches the registers the entities of one heat pump subscribed to."""

    def __init__(self, hass, entry: ConfigEntry):
        """Initialize."""
        self.thermia = create_client(entry.data)
        self.kind = entry.data[CONF_MODEL]
        self.entry_id = entry.entry_id
        self.attributes = {}
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=MODEL_NAMES[self.kind],
            manufacturer=ATTR_MANUFACTURER,
            model=MODEL_NAMES[self.kind],
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

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
        return data

    def registerAttribute(self, attribute):
        if type(attribute) is list:
            for name in attribute:
                _LOGGER.debug("Register attribute for update: %s", name)
                self.attributes[name] = True
        else:
            _LOGGER.debug("Register attribute for update: %s", attribute)
            self.attributes[attribute] = True
