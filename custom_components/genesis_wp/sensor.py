import logging
import re
from functools import lru_cache
from numbers import Number

from genesis_wp.const import KEY_KIND
from genesis_wp.const import KEY_UNIT
from genesis_wp.const import REG_INPUT
from genesis_wp.const import KEY_REG_TYPE
from genesis_wp.const import REG_HOLDING
from genesis_wp.const import REGISTERS
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .register_entity import RegisterAnchor

from .const import ATTR_ICON
from .const import ATTR_LABEL
from .const import CORE_SETTINGS
from .const import SETTING_NAMES
from .const import CURVE_X
from .const import DOMAIN
from .const import HEATPUMP_ALARMS
from .const import HEATPUMP_ATTRIBUTES
from .const import HEATING_CURVES
from .const import HEATPUMP_SENSOR
from .const import OUTDOOR_TEMPERATURE
from .const import REGISTER_EXCLUSIONS
from .const import REGISTER_OVERRIDES
from .const import SENSOR_TYPES
from .const import SETTING_DEPENDENCIES

_LOGGER = logging.getLogger(__name__)

# DHF-REQ: genesis-wp-ha/requirement-17
KIND_CLASSES = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "temperature_delta": None,
    "pressure": SensorDeviceClass.PRESSURE,
    "power": SensorDeviceClass.POWER,
    "energy": SensorDeviceClass.ENERGY,
    "current": SensorDeviceClass.CURRENT,
    "voltage": SensorDeviceClass.VOLTAGE,
    "duration": SensorDeviceClass.DURATION,
    "percent": None,
    "speed": None,
    "count": None,
    "dimensionless": None,
    "state": None,
}


@lru_cache(maxsize=None)
def _warn_unknown_kind(register, value_kind):
    """Warn once per register/kind pair, including across entry reloads."""
    _LOGGER.warning("Register %s has unknown value kind %r; using a plain sensor", register, value_kind)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the heat pump's sensors from a config_entry, except those of absent modules (requirement-12)."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [ThermiaHeatpumpSensor(coordinator, HEATPUMP_SENSOR)]
    for register, spec in REGISTERS.items():
        if not spec[coordinator.kind] or register in coordinator.excluded or register in REGISTER_EXCLUSIONS:
            continue
        if spec[KEY_REG_TYPE] == REG_INPUT:
            sensors.append(ThermiaGenericSensor(coordinator, register))
        elif spec[KEY_REG_TYPE] == REG_HOLDING:
            sensors.append(ThermiaSettingSensor(coordinator, register))
    sensors.extend(FlowSensor(coordinator, key) for key in coordinator.flow_estimators)
    if coordinator.supports_hc2_return:
        sensors.append(HC2ReturnSensor(coordinator))
    async_add_entities(sensors, False)
    coordinator.setup_entity_ids["sensor"] = {sensor.unique_id for sensor in sensors}


class RegisterSensor(RegisterAnchor, SensorEntity):
    """A sensor fed by registers of the coordinator's last update."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator, kind):
        """Initialize."""
        self.coordinator = coordinator
        self.kind = kind
        self._attr_unique_id = coordinator.unique_id(kind)
        self._attr_device_info = coordinator.device_info_for(kind)
        self._attr_entity_category = coordinator.entity_category_for(kind)
        if kind in REGISTERS:
            spec = REGISTERS[kind]
            override = REGISTER_OVERRIDES.get(kind, {})
            self._value_kind = override.get("kind", spec.get(KEY_KIND, {}).get(coordinator.kind))
            self._attr_native_unit_of_measurement = override.get("unit", spec.get(KEY_UNIT, {}).get(coordinator.kind))
            self._attr_device_class = KIND_CLASSES.get(self._value_kind)
            self._attr_state_class = (
                SensorStateClass.TOTAL_INCREASING if self._value_kind == "energy"
                else None if self._value_kind == "state"
                else SensorStateClass.MEASUREMENT
            )
            if self._value_kind not in KIND_CLASSES:
                _warn_unknown_kind(kind, self._value_kind)

    def _subscribed(self):
        return [self.kind]

    def _use_core_setting(self):
        """Keep the established core setting name and default visibility."""
        self._attr_name = CORE_SETTINGS[self.kind]
        self._attr_entity_registry_enabled_default = True

    @property
    def state_class(self):
        """Unknown kinds support statistics only while their value is numeric."""
        if getattr(self, "_value_kind", "state") not in KIND_CLASSES:
            value = self.coordinator.data.get(self.kind)
            return SensorStateClass.MEASUREMENT if isinstance(value, Number) and not isinstance(value, bool) else None
        return self._attr_state_class

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
        self._attr_device_info = coordinator.device_info
        self._attr_entity_category = None

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
        meta = SENSOR_TYPES.get(kind, {})
        self._attr_name = meta.get(ATTR_LABEL, kind.removeprefix("input_").replace("_", " ").title())
        self._attr_icon = meta.get(ATTR_ICON, "mdi:gauge").replace("mdi-", "mdi:")
        if kind in CORE_SETTINGS:
            self._use_core_setting()

    def _subscribed(self):
        curve = HEATING_CURVES.get(self.kind)
        if curve is None:
            return [self.kind]
        return [self.kind, OUTDOOR_TEMPERATURE, *CURVE_X, *curve]

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data.get(self.kind)

    @property
    def extra_state_attributes(self):
        """A set temperature carries its circuit's heating curve and the outdoor temperature for the card."""
        curve = HEATING_CURVES.get(self.kind)
        if curve is None:
            return None
        coordinator = self.coordinator
        if coordinator.data is None:
            return None
        return {
            "curve": [
                [coordinator.data[x], coordinator.data[y]]
                for x, y in zip(CURVE_X, curve)
                if coordinator.has_value(x) and coordinator.has_value(y)
            ],
            "outdoor_temperature": (
                coordinator.data[OUTDOOR_TEMPERATURE] if coordinator.has_value(OUTDOOR_TEMPERATURE) else None
            ),
        }


class ThermiaSettingSensor(RegisterSensor):
    """One holding register, a heat pump setting, shown read-only."""

    _attr_icon = "mdi:tune"

    def __init__(self, coordinator, kind):
        """Initialize."""
        super().__init__(coordinator, kind)
        self._attr_name = SETTING_NAMES.get(kind, kind.removeprefix("holding_").replace("_", " ").title())
        if kind in CORE_SETTINGS:
            self._use_core_setting()

    def _subscribed(self):
        return [self.kind, *SETTING_DEPENDENCIES.get(self.kind, ())]

    @property
    def native_value(self):
        """Return the state."""
        return self.coordinator.data.get(self.kind)


# DHF-REQ: genesis-wp-ha/requirement-26
# The names say the value is an estimate (issue-23); the chips keep their short labels.
FLOW_NAMES = {"condenser_flow": "Estimated condenser flow", "brine_flow": "Estimated brine flow"}


class FlowSensor(SensorEntity):
    """A loop's estimated flow from the library's FlowEstimator held by the coordinator.

    Unknown while the estimator has no value (no calculated window and no calibration yet),
    never 0. The frontend anchor is ``derived_<key>``, alongside the register entities.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    _attr_suggested_display_precision = 1
    _attr_entity_registry_enabled_default = True
    _unrecorded_attributes = frozenset({"register", "calibration"})

    def __init__(self, coordinator, key):
        """Initialize; the sensor sits on the heat pump's internal device with the loop's pump."""
        self.coordinator = coordinator
        self.key = key
        self._attr_name = FLOW_NAMES[key]
        self._attr_unique_id = f"{coordinator.entry_id}_derived_{key}"
        loop = coordinator.flow_estimators[key].loop
        self._attr_device_info = coordinator.device_info_for(loop.pump)

    @property
    def capability_attributes(self):
        """Frontend anchor, present even while the state is unknown."""
        return {**(super().capability_attributes or {}), "register": f"derived_{self.key}"}

    @property
    def available(self):
        """Unavailable only when the last update failed; no estimate yet is unknown, not unavailable."""
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        """The estimated flow [L/min], or None."""
        estimate = self.coordinator.flows.get(self.key)
        return None if estimate is None else estimate.value

    @property
    def extra_state_attributes(self):
        """How the value was obtained and the learned calibration [L/min per %]."""
        estimate = self.coordinator.flows.get(self.key)
        if estimate is None:
            return {"source": "unknown", "calibration": None}
        return {"source": estimate.source, "calibration": estimate.calibration}

    async def async_added_to_hass(self):
        """Follow coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

# DHF-REQ: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-118
class HC2ReturnSensor(CoordinatorEntity, SensorEntity):
    """The estimated heating circuit 2 return temperature."""

    _attr_has_entity_name = True
    _attr_name = "Estimated circuit 2 return"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _unrecorded_attributes = frozenset({"register"})

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_derived_hc2_return"
        self._attr_device_info = coordinator.device_info_for(coordinator.flow_estimators["condenser_flow"].loop.pump)

    # DHF-REQ: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-119
    @property
    def capability_attributes(self):
        """Expose the configured flow even while the return estimate is unavailable."""
        return {
            **(super().capability_attributes or {}),
            "register": "derived_hc2_return",
            "circuit_flow": self.coordinator.circuit_flow,
        }

    @property
    def available(self):
        return super().available and self.native_value is not None

    @property
    def native_value(self):
        return self.coordinator.hc2_return.value

    @property
    def extra_state_attributes(self):
        return {
            "source": "estimate",
            "heat": self.coordinator.hc2_return.heat,
        }
