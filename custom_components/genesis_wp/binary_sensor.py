import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from genesis_wp.const import KEY_REG_TYPE
from genesis_wp.const import REG_COIL
from genesis_wp.const import REGISTERS

from .const import ATTR_CLASS
from .const import ATTR_DEFAULT_ENABLED
from .const import ATTR_LABEL
from .const import BINARY_SENSOR_TYPES
from .const import COMMAND_COILS
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add Thermia entities from a config_entry, except those of absent modules (requirement-12)."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []

    device_info = coordinator.device_info

    for sensor in BINARY_SENSOR_TYPES:
        if REGISTERS[sensor][coordinator.kind] and sensor not in coordinator.excluded:
            sensors.append(ThermiaBinarySensor(coordinator, sensor, device_info))
    for register, spec in REGISTERS.items():
        if (
            spec[KEY_REG_TYPE] == REG_COIL
            and spec[coordinator.kind]
            and register not in COMMAND_COILS
            and register not in coordinator.excluded
        ):
            sensors.append(ThermiaCoilSensor(coordinator, register))
    async_add_entities(sensors, False)


class ThermiaCoilSensor(BinarySensorEntity):
    """One state coil, an enable setting, shown read-only."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:toggle-switch-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, kind):
        """Initialize."""
        self.coordinator = coordinator
        self.kind = kind
        self._attr_unique_id = coordinator.unique_id(kind)
        self._attr_device_info = coordinator.device_info
        self._attr_name = kind.removeprefix("coil_").replace("_", " ").title()

    @property
    def is_on(self):
        """Return the state."""
        return self.coordinator.data.get(self.kind)

    @property
    def available(self):
        """Unavailable when the update failed, or this coil is not fitted or was not read."""
        return self.coordinator.last_update_success and self.coordinator.has_value(self.kind)

    async def async_added_to_hass(self):
        """Subscribe the coil and follow coordinator updates."""
        await super().async_added_to_hass()
        self.coordinator.registerAttribute([self.kind])
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class ThermiaBinarySensor(BinarySensorEntity):
    """Define a Thermia generic sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, kind, device_info):
        """Initialize."""
        self._name = f"{BINARY_SENSOR_TYPES[kind][ATTR_LABEL]}"
        # self._name = f"{coordinator.data[ATTR_MODEL]} {SENSOR_TYPES[kind][ATTR_LABEL]}"
        self._unique_id = coordinator.unique_id(kind)
        self._device_info = device_info
        self.coordinator = coordinator
        self.kind = kind
        self._attrs = {}

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def is_on(self):
        """Return the state."""
        val = self.coordinator.data.get(self.kind)
        return val

    @property
    def device_class(self):
        """Return the device class."""
        if ATTR_CLASS not in BINARY_SENSOR_TYPES[self.kind]:
            return None
        return BINARY_SENSOR_TYPES[self.kind][ATTR_CLASS]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.has_value(self.kind)

    @property
    def should_poll(self):
        """Return the polling requirement of the entity."""
        return False

    @property
    def device_info(self):
        """Return the device info."""
        return self._device_info

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return BINARY_SENSOR_TYPES[self.kind][ATTR_DEFAULT_ENABLED]

    def async_write_ha_state(self):
        super().async_write_ha_state()

    async def async_added_to_hass(self):
        self.coordinator.registerAttribute(self.kind)
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update Thermia entity."""
        await self.coordinator.async_request_refresh()
