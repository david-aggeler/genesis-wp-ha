import logging
import re

from genesis_wp.const import KEY_REG_TYPE
from genesis_wp.const import REG_HOLDING
from genesis_wp.const import REGISTERS
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE

from .const import ATTR_CLASS
from .const import ATTR_DEFAULT_ENABLED
from .const import ATTR_ICON
from .const import ATTR_LABEL
from .const import ATTR_STATE_CLASS
from .const import ATTR_UNIT
from .const import CORE_SETTINGS
from .const import DOMAIN
from .const import HEATPUMP_ALARMS
from .const import HEATPUMP_ATTRIBUTES
from .const import HEATPUMP_SENSOR
from .const import SENSOR_TYPES
from .const import SETTING_DEPENDENCIES
from .const import UNIT_AMPERE
from .const import UNIT_ENERGY
from .const import UNIT_HOURS
from .const import UNIT_KILOWATT
from .const import UNIT_TEMPERATURE
from .const import UNIT_VOLTAGE
from .const import UNIT_WATT

_LOGGER = logging.getLogger(__name__)

# Device and state class follow the unit unless a SENSOR_TYPES entry names them.
UNIT_CLASSES = {
    UNIT_TEMPERATURE: (SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    UNIT_KILOWATT: (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    UNIT_WATT: (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    UNIT_VOLTAGE: (SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    UNIT_AMPERE: (SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    UNIT_ENERGY: (SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    UNIT_HOURS: (SensorDeviceClass.DURATION, SensorStateClass.TOTAL_INCREASING),
    PERCENTAGE: (None, SensorStateClass.MEASUREMENT),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the heat pump's sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [ThermiaHeatpumpSensor(coordinator, HEATPUMP_SENSOR)]
    for sensor in SENSOR_TYPES:
        if REGISTERS[sensor][coordinator.kind]:
            sensors.append(ThermiaGenericSensor(coordinator, sensor))
    for register, spec in REGISTERS.items():
        if spec[KEY_REG_TYPE] == REG_HOLDING and spec[coordinator.kind]:
            sensors.append(ThermiaSettingSensor(coordinator, register))
    async_add_entities(sensors, False)


class RegisterSensor(SensorEntity):
    """A sensor fed by registers of the coordinator's last update."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator, kind):
        """Initialize."""
        self.coordinator = coordinator
        self.kind = kind
        self._attr_unique_id = coordinator.unique_id(kind)
        self._attr_device_info = coordinator.device_info

    def _subscribed(self):
        return [self.kind]

    def _use_core_setting(self):
        """A default-enabled set temperature: interim name, °C."""
        self._attr_name = CORE_SETTINGS[self.kind]
        self._attr_native_unit_of_measurement = UNIT_TEMPERATURE
        self._attr_device_class, self._attr_state_class = UNIT_CLASSES[UNIT_TEMPERATURE]
        self._attr_entity_registry_enabled_default = True

    @property
    def icon(self):
        """Leave the icon to Home Assistant when a device class names the quantity; else the fallback."""
        if self.device_class is not None:
            return None
        return super().icon

    @property
    def suggested_object_id(self):
        """Spell a negative number as minus: slugify would drop the sign of '-5 °C'."""
        name = super().suggested_object_id
        return re.sub(r"-(?=\d)", "minus ", name) if isinstance(name, str) else name

    @property
    def available(self):
        """Unavailable when the update failed, or this register is not fitted or was not read."""
        return self.coordinator.last_update_success and self.coordinator.has_value(self.kind)

    async def async_added_to_hass(self):
        """Subscribe the registers and follow coordinator updates."""
        await super().async_added_to_hass()
        self.coordinator.registerAttribute(self._subscribed())
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the heat pump entity."""
        await self.coordinator.async_request_refresh()


class ThermiaHeatpumpSensor(RegisterSensor):
    """The heat pump's operating state, with the main readings as attributes."""

    _attr_name = "Heatpump"
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, kind):
        """Initialize."""
        super().__init__(coordinator, kind)
        self._attr_unique_id = f"{coordinator.entry_id}_heatpump"

    def _subscribed(self):
        return [self.kind, *(attr[0] for attr in HEATPUMP_ATTRIBUTES), *HEATPUMP_ALARMS]

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data.get(self.kind)

    @property
    def extra_state_attributes(self):
        """Return the main readings."""
        attrs = {}
        for attr in HEATPUMP_ATTRIBUTES:
            label = (attr[0].split("_", 1)[-1]).title()
            val = self.coordinator.data.get(attr[0])
            if attr[1] and val is not None:
                val = f"{val} {attr[1]}"
            attrs[label] = val
        if self.has_alarm():
            attrs["Active alarms"] = ""
        return attrs

    @property
    def icon(self):
        """Return the icon."""
        if self.has_alarm():
            return "mdi:alert"
        return "mdi:pulse"

    def has_alarm(self):
        return any(self.coordinator.data.get(alarm) for alarm in HEATPUMP_ALARMS)


class ThermiaGenericSensor(RegisterSensor):
    """One register as a sensor."""

    def __init__(self, coordinator, kind):
        """Initialize."""
        super().__init__(coordinator, kind)
        meta = SENSOR_TYPES[kind]
        unit = meta.get(ATTR_UNIT)
        device_class, state_class = UNIT_CLASSES.get(unit, (None, None))
        self._attr_name = meta[ATTR_LABEL]
        self._attr_icon = meta[ATTR_ICON].replace("mdi-", "mdi:")
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = meta.get(ATTR_CLASS, device_class)
        self._attr_state_class = meta.get(ATTR_STATE_CLASS, state_class)
        self._attr_entity_registry_enabled_default = meta[ATTR_DEFAULT_ENABLED]
        if kind in CORE_SETTINGS:
            self._use_core_setting()

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data.get(self.kind)


class ThermiaSettingSensor(RegisterSensor):
    """One holding register, a heat pump setting, shown read-only."""

    _attr_icon = "mdi:tune"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, kind):
        """Initialize."""
        super().__init__(coordinator, kind)
        self._attr_name = kind.removeprefix("holding_").replace("_", " ").title()
        if kind in CORE_SETTINGS:
            self._use_core_setting()

    def _subscribed(self):
        return [self.kind, *SETTING_DEPENDENCIES.get(self.kind, ())]

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data.get(self.kind)
