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
from homeassistant.components.sensor import RestoreSensor
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfPower
from homeassistant.const import UnitOfTemperature
from homeassistant.const import UnitOfTime
from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import RestoredExtraData
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import COMPRESSOR_SIGNAL
from .buffer_use import CURVE_INPUTS
from .cycles import HOT_WATER, mean_band, run_band

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

    sensors = [
        ThermiaHeatpumpSensor(coordinator, HEATPUMP_SENSOR),
        DisabledEntitiesSensor(coordinator),
    ]
    for register, spec in REGISTERS.items():
        if not spec[coordinator.kind] or register in coordinator.excluded or register in REGISTER_EXCLUSIONS:
            continue
        if spec[KEY_REG_TYPE] == REG_INPUT:
            sensors.append(ThermiaGenericSensor(coordinator, register))
        elif spec[KEY_REG_TYPE] == REG_HOLDING:
            sensors.append(ThermiaSettingSensor(coordinator, register))
    sensors.extend(FlowSensor(coordinator, key) for key in coordinator.flow_estimators)
    if coordinator.supports_hc2_return:
        sensors.extend((HC2ReturnSensor(coordinator), RoomHeatSensor(coordinator)))
    if coordinator.rooms_heat is not None:
        sensors.append(
            DailyHeatSensor(coordinator, "heat_to_rooms_today", coordinator.rooms_heat, report_coverage=True)
        )
    if coordinator.produced_heat is not None:
        sensors.append(DailyHeatSensor(coordinator, "heat_produced_today", coordinator.produced_heat))
    if coordinator.run_tracker is not None:
        sensors.extend(CompressorRunSensor(coordinator, key) for key in COMPRESSOR_STATISTICS)
    if coordinator.buffer_use is not None:
        sensors.extend((
            LastDischargeSensor(coordinator),
            DailyDischargeSensor(coordinator),
            BufferJudgementSensor(coordinator),
        ))
    if coordinator.supports_curve_gap:
        sensors.append(CurveGapSensor(coordinator))
    async_add_entities(sensors, False)
    coordinator.setup_entity_ids["sensor"] = {sensor.unique_id for sensor in sensors}


# DHF-REQ: genesis-wp-ha/requirement-35
class DisabledEntitiesSensor(SensorEntity):
    """Count disabled entities from this config entry for the drawing notice."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "disabled_entities"
    _attr_icon = "mdi:counter"
    _attr_extra_state_attributes = {"genesis_wp_diagnostic": "disabled_entities"}

    def __init__(self, coordinator):
        self._entry_id = coordinator.entry_id
        self._attr_unique_id = f"{self._entry_id}_disabled_entities"
        self._attr_device_info = coordinator.device_info

    async def async_added_to_hass(self):
        registry = er.async_get(self.hass)

        def is_counted(entity):
            return (
                entity is not None
                and entity.config_entry_id == self._entry_id
                and entity.disabled_by is not None
                and entity.unique_id != self.unique_id
            )

        disabled_ids = {
            entity.entity_id
            for entity in er.async_entries_for_config_entry(registry, self._entry_id)
            if is_counted(entity)
        }
        self._attr_native_value = len(disabled_ids)

        @callback
        def registry_updated(event):
            entity_id = event.data["entity_id"]
            disabled_ids.discard(event.data.get("old_entity_id", entity_id))
            if is_counted(registry.async_get(entity_id)):
                disabled_ids.add(entity_id)
            count = len(disabled_ids)
            if count != self._attr_native_value:
                self._attr_native_value = count
                self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, registry_updated)
        )


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
    _flow_attributes = (
        "hot_port_flow", "bypass_flow", "buffer_return_flow",
        "heat_pump_return_flow", "either_way_flow",
    )
    _unrecorded_attributes = frozenset(("register", *_flow_attributes))

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

    # DHF-REQ: genesis-wp-ha/requirement-27 genesis-wp-ha/ac-194 genesis-wp-ha/ac-195
    @property
    def extra_state_attributes(self):
        estimate = self.coordinator.hc2_return
        attributes = {"source": "estimate", "heat": estimate.heat}
        for key in self._flow_attributes:
            flow = getattr(estimate, key)
            rounded = round(flow, 2) if flow is not None else None
            # Preserve the direction and activity of flows below display precision.
            attributes[key] = flow if rounded == 0 else rounded
        return attributes


class HeatSensor(CoordinatorEntity, SensorEntity):
    """A heat balance measurement on the internal heat pump device."""

    _attr_has_entity_name = True
    _attr_suggested_display_precision = 2
    _unrecorded_attributes = frozenset({"register"})

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self._attr_translation_key = f"derived_{key}"
        self._attr_unique_id = f"{coordinator.entry_id}_{self._attr_translation_key}"
        self._attr_device_info = coordinator.device_info_for(COMPRESSOR_SIGNAL)

    @property
    def capability_attributes(self):
        return {**(super().capability_attributes or {}), "register": self._attr_translation_key}


# DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-137
class RoomHeatSensor(HeatSensor):
    """Instantaneous heating circuit 2 heat from the library estimator."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator):
        super().__init__(coordinator, "heat_to_rooms")

    @property
    def native_value(self):
        return self.coordinator.hc2_return.heat

    @property
    def available(self):
        return super().available and self.native_value is not None


# DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-140
class DailyHeatSensor(HeatSensor, RestoreSensor):
    """A restorable local-day energy counter."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, key, tracker, *, report_coverage=False):
        super().__init__(coordinator, key)
        self._tracker = tracker
        self._report_coverage = report_coverage
        self._publish_zero = False

    async def async_added_to_hass(self):
        if (restored := await self.async_get_last_extra_data()) is not None:
            self._tracker.restore(restored.as_dict())
        await super().async_added_to_hass()

    @property
    def extra_restore_state_data(self):
        return RestoredExtraData(self._tracker.snapshot())

    @property
    def native_value(self):
        if self._publish_zero:
            return 0.0
        return self._tracker.energy

    # DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-178
    @property
    def available(self):
        if self._report_coverage and not self.coordinator.rooms_heat_estimable:
            return False
        return super().available

    # DHF-REQ: genesis-wp-ha/requirement-29 genesis-wp-ha/ac-177
    @callback
    def _handle_coordinator_update(self):
        """Publish 0 before the first new-day value, so statistics see the meter reset.

        total_increasing detects a reset only from a drop; a new-day value above the old
        day's final one would otherwise be recorded as the difference only.
        """
        if self._tracker.take_rollover():
            self._publish_zero = True
            self.async_write_ha_state()
            self._publish_zero = False
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self):
        if self._report_coverage:
            return {"coverage": self._tracker.coverage}
        return None


COMPRESSOR_STATISTICS = {
    "starts_today": None,
    "hot_water_starts_today": None,
    "short_heating_runs_today": None,
    "running_hours_today": UnitOfTime.HOURS,
    "heating_run_minimum": UnitOfTime.MINUTES,
    "heating_run_mean": UnitOfTime.MINUTES,
    "heating_run_maximum": UnitOfTime.MINUTES,
    "last_run_length": UnitOfTime.MINUTES,
}


# DHF-REQ: genesis-wp-ha/requirement-28
class CompressorRunSensor(CoordinatorEntity, SensorEntity):
    """A read-only statistic backed by the entry's shared daily compressor runs."""

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({"register"})

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self._key = key
        self._register = f"derived_{key}"
        self._tracker = coordinator.run_tracker
        self._attr_translation_key = self._register
        self._attr_unique_id = f"{coordinator.entry_id}_{self._register}"
        self._attr_device_info = coordinator.device_info_for(COMPRESSOR_SIGNAL)
        self._attr_native_unit_of_measurement = COMPRESSOR_STATISTICS[key]
        if self._attr_native_unit_of_measurement is None:
            self._attr_icon = "mdi:counter"
        else:
            self._attr_device_class = SensorDeviceClass.DURATION

    @property
    def capability_attributes(self):
        return {**(super().capability_attributes or {}), "register": self._register}

    @property
    def native_value(self):
        value = self._tracker.values.get(self._key)
        if value is None or self._attr_native_unit_of_measurement is None:
            return value
        return round(value, 2 if self._key == "running_hours_today" else 1)

    @property
    def extra_state_attributes(self):
        value = self._tracker.values.get(self._key)
        if value is None or self._attr_native_unit_of_measurement != UnitOfTime.MINUTES:
            return None
        if self._key == "heating_run_mean":
            return {"band": mean_band(value)}
        if self._key != "last_run_length":
            return {"band": run_band(value)}
        kind = self._tracker.daily.runs[-1][0]
        # The run-length scale judges heating runs only; a hot-water run has none (design_decision-2, ac-163).
        return {"kind": kind} if kind == HOT_WATER else {"band": run_band(value), "kind": kind}


class BufferDeltaSensor(HeatSensor):
    """A temperature difference in kelvins."""

    _attr_native_unit_of_measurement = "K"
    _attr_state_class = SensorStateClass.MEASUREMENT


class LastDischargeSensor(BufferDeltaSensor):
    """The last completed and eligible buffer discharge phase."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "last_discharge_restart_margin")

    @property
    def native_value(self):
        phase = self.coordinator.buffer_use.last
        return phase.margin if phase is not None else None

    @property
    def extra_state_attributes(self):
        phase = self.coordinator.buffer_use.last
        if phase is None:
            return None
        return {
            "drawn_energy": round(phase.energy, 2) if phase.energy is not None else None,
            "cold_tail_share": round(phase.share, 1),
        }


class DailyDischargeSensor(BufferDeltaSensor, RestoreSensor):
    """The daily median and the individual observations needed after a restart."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "median_restart_margin_today")
        self._evaluator = coordinator.buffer_use

    async def async_added_to_hass(self):
        if (restored := await self.async_get_last_extra_data()) is not None:
            self._evaluator.restore(dt_util.now(), restored.as_dict())
        await super().async_added_to_hass()

    @property
    def extra_restore_state_data(self):
        return RestoredExtraData(self._evaluator.snapshot())

    @property
    def native_value(self):
        return self._evaluator.daily[0]

    @property
    def extra_state_attributes(self):
        _, share = self._evaluator.daily
        return {
            "median_cold_tail_share": round(share, 1) if share is not None else None,
            "phase_count": len(self._evaluator.phases),
        }


class BufferJudgementSensor(HeatSensor):
    """Whether the observed discharges suggest keeping, lowering or raising the reference."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["keep", "lower", "raise"]
    _attr_suggested_display_precision = None

    def __init__(self, coordinator):
        super().__init__(coordinator, "buffer_judgement")

    @property
    def native_value(self):
        return self.coordinator.buffer_use.judgement


# DHF-REQ: genesis-wp-ha/requirement-30 genesis-wp-ha/ac-145
class CurveGapSensor(BufferDeltaSensor):
    """The live difference between the buffer and circuit 2 set points."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "curve_gap")

    @property
    def native_value(self):
        if self.coordinator.thermia.unread.intersection(CURVE_INPUTS):
            return None
        buffer, circuit = (self.coordinator.data.get(key) for key in CURVE_INPUTS)
        return buffer - circuit if buffer is not None and circuit is not None else None

    @property
    def available(self):
        return super().available and self.native_value is not None
