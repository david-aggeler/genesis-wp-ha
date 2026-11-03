import genesis_wp.const as thermiaconst
from homeassistant.const import UnitOfTemperature

ATTR_ICON = "icon"
ATTR_LABEL = "label"
ATTR_MANUFACTURER = "Thermia"
ATTR_STATUS = "status"
ATTR_CLASS = "device_class"
ATTR_UPTIME = "uptime"
ATTR_DEFAULT_ENABLED = "default_enabled"
ATTR_SCALE = "scale"
ATTR_ADDR = "address"

KEY_STATE_ATTRIBUTES = "state_attrs"

UNIT_HOURS = "h"
UNIT_TEMPERATURE = UnitOfTemperature.CELSIUS


DOMAIN = "genesis_wp"

CONF_UNIT = "unit"
CONF_MODEL = "model"
CONF_ADVANCED = "advanced"  # config flow section holding the port; never stored in entry data
CONF_MODE = "mode"  # absent for a real heat pump
CONF_PROFILE = "profile"
CONF_CAPABILITIES = "capabilities"  # emulated: modules switched against the profile, {name: on}
CONF_CAPABILITIES_SEEN = "capabilities_seen"  # modules the library has seen running, kept across reloads
MODE_EMULATED = "emulated"

# Options flow (requirement-14): per module, automatic follows detection; the others are stored in
# entry.options as {capability: library state} and passed to the library as capability overrides.
MODULE_AUTOMATIC = "automatic"
MODULE_INSTALLED = "installed"
MODULE_NOT_INSTALLED = "not_installed"
EMULATOR_HOST = "127.0.0.1"  # the in-process emulator never binds outside loopback
EMULATOR_DYNAMICS_INTERVAL = 5  # seconds between simulated plant steps
DEFAULT_PORT = 502
DEFAULT_UNIT = 1
DEFAULT_MODEL = thermiaconst.MODEL_STIEBEL_WPE_I_071

ICON_DINPUT = "mdi-toggle-switch"
ICON_INPUT = "mdi-gauge"
ICON_HOLDING = "mdi-gauge"
CLASS_RELAY = "opening"
CLASS_ALARM = "problem"
CLASS_STATE = "plug"
CLASS_ENERGY = "energy"

ATTR_STATUS = thermiaconst.ATTR_INPUT_FIRST_PRIORITISED_DEMAND

HEATPUMP_SENSOR = thermiaconst.ATTR_INPUT_FIRST_PRIORITISED_DEMAND
HEATPUMP_ATTRIBUTES = [
    [thermiaconst.ATTR_INPUT_COMPRESSOR_SPEED_RPM, "rpm"],
    [thermiaconst.ATTR_INPUT_COMPRESSOR_CURRENT_GEAR, None],
    [thermiaconst.ATTR_INPUT_QUEUED_DEMAND_SECOND_PRIORITY, None],
    [thermiaconst.ATTR_INPUT_QUEUED_DEMAND_THIRD_PRIORITY, None],
    [thermiaconst.ATTR_INPUT_BRINE_IN_TEMPERATURE, UNIT_TEMPERATURE],
    [thermiaconst.ATTR_INPUT_BRINE_OUT_TEMPERATURE, UNIT_TEMPERATURE],
    [thermiaconst.ATTR_INPUT_COMPRESSOR_OPERATING_HOURS, UNIT_HOURS],
    [thermiaconst.ATTR_INPUT_TAP_WATER_OPERATING_HOURS, UNIT_HOURS],
    [thermiaconst.ATTR_INPUT_EXTERNAL_ADDITIONAL_HEATER_OPERATING_HOURS, UNIT_HOURS],
]
HEATPUMP_ALARMS = [
    thermiaconst.ATTR_DINPUT_ALARM_ACTIVE_CLASS_A,
    thermiaconst.ATTR_DINPUT_ALARM_ACTIVE_CLASS_B,
    thermiaconst.ATTR_DINPUT_ALARM_ACTIVE_CLASS_C,
]

# Coils that trigger an action rather than hold a state; they get no entity.
COMMAND_COILS = {thermiaconst.ATTR_COIL_RESET_ALL_ALARMS}

# Established names of default-enabled core settings, until the library carries
# per-model names (genesis-wp issue-6). Units and classes come from the library.
_CURVE_OUTDOOR = (17, 10, 5, 0, -5, -15, -25)  # heating curve points of the WPE-I display
_POINTS = range(1, len(_CURVE_OUTDOOR) + 1)
CURVE_X = [getattr(thermiaconst, f"ATTR_INPUT_HEAT_CURVE_X_COORDINATE_{point}") for point in _POINTS]
_CURVE_Y_1 = [getattr(thermiaconst, f"ATTR_HOLDING_SET_POINT_HEAT_CURVE_Y_{point}") for point in _POINTS]
_CURVE_Y_2 = [getattr(thermiaconst, f"ATTR_HOLDING_SET_POINT_CURVE_Y_COORDINATE_{point}_MIX_VALVE_1") for point in _POINTS]
_SET_TEMPERATURE_1 = thermiaconst.ATTR_INPUT_SYSTEM_SUPPLY_LINE_CALCULATED_SET_POINT
_SET_TEMPERATURE_2 = thermiaconst.ATTR_INPUT_DESIRED_TEMPERATURE_DISTRIBUTION_CIRCUIT_MIX_VALVE_1
CORE_SETTINGS = {
    _SET_TEMPERATURE_1: "Heating circuit 1 set temperature",
    _SET_TEMPERATURE_2: "Heating circuit 2 set temperature",
    thermiaconst.ATTR_HOLDING_COMFORT_WHEEL_SETTING: "Room set point",
    **{y: f"Heating circuit 1 curve at {outdoor} °C outdoor" for y, outdoor in zip(_CURVE_Y_1, _CURVE_OUTDOOR)},
    **{y: f"Heating circuit 2 curve at {outdoor} °C outdoor" for y, outdoor in zip(_CURVE_Y_2, _CURVE_OUTDOOR)},
}

# A circuit's set temperature sensor carries its heating curve for the card (requirement-11).
HEATING_CURVES = {_SET_TEMPERATURE_1: _CURVE_Y_1, _SET_TEMPERATURE_2: _CURVE_Y_2}
OUTDOOR_TEMPERATURE = thermiaconst.ATTR_INPUT_OUTDOOR_TEMPERATURE
CARD_URL = "/genesis_wp/genesis-wp-heating-curve-card.js"

# Registers a setting entity subscribes besides its own: the library reads holding 116 only
# while it knows coil 41 is True.
SETTING_DEPENDENCIES = {
    thermiaconst.ATTR_HOLDING_FIXED_SYSTEM_SUPPLY_SET_POINT: [
        thermiaconst.ATTR_COIL_ENABLE_FIXED_SYSTEM_SUPPLY_SET_POINT
    ],
}


BINARY_SENSOR_TYPES = {
    thermiaconst.ATTR_DINPUT_ALARM_ACTIVE_CLASS_A: {
        ATTR_LABEL: "Alarm Active Class A",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_ALARM_ACTIVE_CLASS_B: {
        ATTR_LABEL: "Alarm Active Class B",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_ALARM_ACTIVE_CLASS_C: {
        ATTR_LABEL: "Alarm Active Class C",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_ALARM_ACTIVE_CLASS_D: {
        ATTR_LABEL: "Alarm Active Class D",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_ALARM_ACTIVE_CLASS_E: {
        ATTR_LABEL: "Alarm Active Class E",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_HIGH_PRESSURE_SWITCH_ALARM: {
        ATTR_LABEL: "High Pressure Switch Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_LOW_PRESSURE_LEVEL_ALARM: {
        ATTR_LABEL: "Low Pressure Level Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_HIGH_DISCHARGE_PIPE_TEMPERATURE_ALARM: {
        ATTR_LABEL: "High Discharge Pipe Temperature Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_OPERATING_PRESSURE_LIMIT_INDICATION: {
        ATTR_LABEL: "Operating Pressure Limit Indication",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_DISCHARGE_PIPE_SENSOR_ALARM: {
        ATTR_LABEL: "Discharge Pipe Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_LIQUID_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Liquid Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SUCTION_GAS_SENSOR_ALARM: {
        ATTR_LABEL: "Suction Gas Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_FLOW_PRESSURE_SWITCH_ALARM: {
        ATTR_LABEL: "Flow Pressure Switch Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_POWER_INPUT_PHASE_DETECTION_ALARM: {
        ATTR_LABEL: "Power Input Phase Detection Alarm",
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_INVERTER_UNIT_ALARM: {
        ATTR_LABEL: "Inverter Unit Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SYSTEM_SUPPLY_LOW_TEMPERATURE_ALARM: {
        ATTR_LABEL: "System Supply Low Temperature Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COMPRESSOR_LOW_SPEED_ALARM: {
        ATTR_LABEL: "Compressor Low Speed Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_LOW_SUPER_HEAT_ALARM: {
        ATTR_LABEL: "Low Super Heat Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_PRESSURE_RATIO_OUT_OF_RANGE_ALARM: {
        ATTR_LABEL: "Pressure Ratio Out Of Range Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COMPRESSOR_PRESSURE_OUTSIDE_ENVELOPE_ALARM: {
        ATTR_LABEL: "Compressor Pressure Outside Envelope Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_BRINE_TEMPERATURE_OUT_OF_RANGE_ALARM: {
        ATTR_LABEL: "Brine Temperature Out Of Range Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_BRINE_IN_SENSOR_ALARM: {
        ATTR_LABEL: "Brine In Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_BRINE_OUT_SENSOR_ALARM: {
        ATTR_LABEL: "Brine Out Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_CONDENSER_IN_SENSOR_ALARM: {
        ATTR_LABEL: "Condenser In Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_CONDENSER_OUT_SENSOR_ALARM: {
        ATTR_LABEL: "Condenser Out Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_OUTDOOR_SENSOR_ALARM: {
        ATTR_LABEL: "Outdoor Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SYSTEM_SUPPLY_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "System Supply Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_1_SUPPLY_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Mix Valve 1 Supply Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_2_SUPPLY_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Mix Valve 2 Supply Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_3_SUPPLY_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Mix Valve 3 Supply Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_4_SUPPLY_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Mix Valve 4 Supply Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_5_SUPPLY_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Mix Valve 5 Supply Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_WCS_RETURN_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Wcs Return Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_TWC_SUPPLY_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Twc Supply Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COOLING_TANK_SENSOR_ALARM: {
        ATTR_LABEL: "Cooling Tank Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COOLING_SUPPLY_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Cooling Supply Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COOLING_CIRCUIT_RETURN_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Cooling Circuit Return Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_BRINE_DELTA_OUT_OF_RANGE_ALARM: {
        ATTR_LABEL: "Brine Delta Out Of Range Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_TAP_WATER_MID_SENSOR_ALARM: {
        ATTR_LABEL: "Tap Water Mid Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_TWC_CIRCULATION_RETURN_SENSOR_ALARM: {
        ATTR_LABEL: "Twc Circulation Return Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_HGW_SENSOR_ALARM: {
        ATTR_LABEL: "Hgw Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_INTERNAL_ADDITIONAL_HEATER_ALARM: {
        ATTR_LABEL: "Internal Additional Heater Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_BRINE_IN_HIGH_TEMPERATURE_ALARM: {
        ATTR_LABEL: "Brine In High Temperature Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_BRINE_IN_LOW_TEMPERATURE_ALARM: {
        ATTR_LABEL: "Brine In Low Temperature Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_BRINE_OUT_LOW_TEMPERATURE_ALARM: {
        ATTR_LABEL: "Brine Out Low Temperature Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_TWC_CIRCULATION_RETURN_LOW_TEMPERATURE_ALARM: {
        ATTR_LABEL: "Twc Circulation Return Low Temperature Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_TWC_SUPPLY_LOW_TEMPERATURE_ALARM: {
        ATTR_LABEL: "Twc Supply Low Temperature Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_1_SUPPLY_TEMPERATURE_DEVIATION_ALARM: {
        ATTR_LABEL: "Mix Valve 1 Supply Temperature Deviation Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_2_SUPPLY_TEMPERATURE_DEVIATION_ALARM: {
        ATTR_LABEL: "Mix Valve 2 Supply Temperature Deviation Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_3_SUPPLY_TEMPERATURE_DEVIATION_ALARM: {
        ATTR_LABEL: "Mix Valve 3 Supply Temperature Deviation Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_4_SUPPLY_TEMPERATURE_DEVIATION_ALARM: {
        ATTR_LABEL: "Mix Valve 4 Supply Temperature Deviation Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_5_SUPPLY_TEMPERATURE_DEVIATION_ALARM: {
        ATTR_LABEL: "Mix Valve 5 Supply Temperature Deviation Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_WCS_RETURN_LINE_TEMPERATURE_DEVIATION_ALARM: {
        ATTR_LABEL: "Wcs Return Line Temperature Deviation Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SUM_ALARM: {
        ATTR_LABEL: "Sum Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COOLING_CIRCUIT_SUPPLY_LINE_TEMPERATURE_DEVIATION_ALARM: {
        ATTR_LABEL: "Cooling Circuit Supply Line Temperature Deviation Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COOLING_TANK_TEMPERATURE_DEVIATION_ALARM: {
        ATTR_LABEL: "Cooling Tank Temperature Deviation Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SURPLUS_HEAT_TEMPERATURE_DEVIATION_ALARM: {
        ATTR_LABEL: "Surplus Heat Temperature Deviation Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_HUMIDITY_ROOM_SENSOR_ALARM: {
        ATTR_LABEL: "Humidity Room Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SURPLUS_HEAT_SUPPLY_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Surplus Heat Supply Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SURPLUS_HEAT_RETURN_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Surplus Heat Return Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COOLING_TANK_RETURN_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Cooling Tank Return Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_TEMPERATURE_ROOM_SENSOR_ALARM: {
        ATTR_LABEL: "Temperature Room Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_INVERTER_UNIT_COMMUNICATION_ALARM: {
        ATTR_LABEL: "Inverter Unit Communication Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_POOL_RETURN_LINE_SENSOR_ALARM: {
        ATTR_LABEL: "Pool Return Line Sensor Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_EXTERNAL_STOP_FOR_POOL: {
        ATTR_LABEL: "External Stop For Pool",
        ATTR_CLASS: CLASS_RELAY,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_EXTERNAL_START_BRINE_PUMP: {
        ATTR_LABEL: "External Start Brine Pump",
        ATTR_CLASS: CLASS_RELAY,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_EXTERNAL_RELAY_FOR_BRINE_GROUND_WATER_PUMP: {
        ATTR_LABEL: "External Relay For Brine Ground Water Pump",
        ATTR_CLASS: CLASS_RELAY,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_TAP_WATER_END_TANK_SENSOR_ALARM: {
        ATTR_LABEL: "Tap Water End Tank Sensor Alarm",
        ATTR_CLASS: CLASS_RELAY,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MAXIMUM_TIME_FOR_ANTI_LEGIONELLA_EXCEEDED_ALARM: {
        ATTR_LABEL: "Maximum Time For Anti Legionella Exceeded Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_GENESIS_SECONDARY_UNIT_ALARM: {
        ATTR_LABEL: "Genesis Secondary Unit Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_PRIMARY_UNIT_CONFLICT_ALARM: {
        ATTR_LABEL: "Primary Unit Conflict Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_PRIMARY_UNIT_NO_SECONDARY_ALARM: {
        ATTR_LABEL: "Primary Unit No Secondary Alarm",
        ATTR_CLASS: CLASS_ALARM,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_OIL_BOOST_IN_PROGRESS: {
        ATTR_LABEL: "Oil Boost In Progress",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COMPRESSOR_CONTROL_SIGNAL: {
        ATTR_LABEL: "Compressor Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SMART_GRID_1: {
        ATTR_LABEL: "Smart Grid 1",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_EXTERNAL_ALARM_INPUT: {
        ATTR_LABEL: "External Alarm Input",
        ATTR_CLASS: CLASS_RELAY,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SMART_GRID_2: {
        ATTR_LABEL: "Smart Grid 2",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_EXTERNAL_ADDITIONAL_HEATER_CONTROL_SIGNAL: {
        ATTR_LABEL: "External Additional Heater Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_MIX_VALVE_1_CIRCULATION_PUMP_CONTROL_SIGNAL: {
        ATTR_LABEL: "Mix Valve 1 Circulation Pump Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_CONDENSER_PUMP_ON_OFF_CONTROL: {
        ATTR_LABEL: "Condenser Pump On Off Control",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SYSTEM_CIRCULATION_PUMP_CONTROL_SIGNAL: {
        ATTR_LABEL: "System Circulation Pump Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_HOT_GAS_CIRCULATION_PUMP_CONTROL_SIGNAL: {
        ATTR_LABEL: "Hot Gas Circulation Pump Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_BRINE_PUMP_ON_OFF_CONTROL: {
        ATTR_LABEL: "Brine Pump On Off Control",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_EXTERNAL_HEATER_CIRCULATION_PUMP_CONTROL_SIGNAL: {
        ATTR_LABEL: "External Heater Circulation Pump Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_HEATING_SEASON_ACTIVE: {
        ATTR_LABEL: "Heating Season Active",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_EXTERNAL_ADDITIONAL_HEATER_ACTIVE: {
        ATTR_LABEL: "External Additional Heater Active",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_INTERNAL_ADDITIONAL_HEATER_ACTIVE: {
        ATTR_LABEL: "Internal Additional Heater Active",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_HGW_REGULATION_CONTROL_SIGNAL: {
        ATTR_LABEL: "Hgw Regulation Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_HEAT_PUMP_STOPPING: {
        ATTR_LABEL: "Heat Pump Stopping",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_HEAT_PUMP_OK_TO_START: {
        ATTR_LABEL: "Heat Pump Ok To Start",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_TWC_SUPPLY_LINE_CIRCULATION_PUMP_CONTROL_SIGNAL: {
        ATTR_LABEL: "Twc Supply Line Circulation Pump Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_WCS_REGULATION_CONTROL_SIGNAL: {
        ATTR_LABEL: "Wcs Regulation Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_WCS_CIRCULATION_PUMP_CONTROL_SIGNAL: {
        ATTR_LABEL: "Wcs Circulation Pump Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_TWC_END_TANK_HEATER_CONTROL_SIGNAL: {
        ATTR_LABEL: "Twc End Tank Heater Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_POOL_DIRECTIONAL_VALVE_POSITION: {
        ATTR_LABEL: "Pool Directional Valve Position",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COOLING_CIRCUIT_CIRCULATION_PUMP_CONTROL_SIGNAL: {
        ATTR_LABEL: "Cooling Circuit Circulation Pump Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_POOL_CIRCULATION_PUMP_CONTROL_SIGNAL: {
        ATTR_LABEL: "Pool Circulation Pump Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SURPLUS_HEAT_DIRECTIONAL_VALVE_POSITION: {
        ATTR_LABEL: "Surplus Heat Directional Valve Position",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SURPLUS_HEAT_CIRCULATION_PUMP_CONTROL_SIGNAL: {
        ATTR_LABEL: "Surplus Heat Circulation Pump Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COOLING_CIRCUIT_REGULATION_CONTROL_SIGNAL: {
        ATTR_LABEL: "Cooling Circuit Regulation Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_SURPLUS_HEAT_REGULATION_CONTROL_SIGNAL: {
        ATTR_LABEL: "Surplus Heat Regulation Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_ACTIVE_COOLING_DIRECTIONAL_VALVE_POSITION: {
        ATTR_LABEL: "Active Cooling Directional Valve Position",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_PASSIVE_ACTIVE_COOLING_DIRECTIONAL_VALVE_POSITION: {
        ATTR_LABEL: "Passive Active Cooling Directional Valve Position",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_POOL_REGULATION_CONTROL_SIGNAL: {
        ATTR_LABEL: "Pool Regulation Control Signal",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_INDICATION_WHEN_MIXING_VALVE_1_IS_PRODUCING_PASSIVE_COOLING: {
        ATTR_LABEL: "Indication When Mixing Valve 1 Is Producing Passive Cooling",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
    thermiaconst.ATTR_DINPUT_COMPRESSOR_IS_UNABLE_TO_SPEED_UP: {
        ATTR_LABEL: "Compressor Is Unable To Speed Up",
        ATTR_CLASS: CLASS_STATE,
        ATTR_DEFAULT_ENABLED: False,
    },
}

SENSOR_TYPES = {
    thermiaconst.ATTR_INPUT_FIRST_PRIORITISED_DEMAND: {
        ATTR_LABEL: "First Prioritised Demand",
    },
    thermiaconst.ATTR_INPUT_COMPRESSOR_AVAILABLE_GEARS: {
        ATTR_LABEL: "Compressor Available Gears",
    },
    thermiaconst.ATTR_INPUT_COMPRESSOR_SPEED_RPM: {
        ATTR_LABEL: "Compressor Speed Rpm",
    },
    thermiaconst.ATTR_INPUT_EXTERNAL_ADDITIONAL_HEATER_CURRENT_DEMAND: {
        ATTR_LABEL: "External Additional Heater Current Demand",
    },
    thermiaconst.ATTR_INPUT_DISCHARGE_PIPE_TEMPERATURE: {
        ATTR_LABEL: "Discharge Pipe Temperature",
    },
    thermiaconst.ATTR_INPUT_CONDENSER_IN_TEMPERATURE: {
        ATTR_LABEL: "Condenser In Temperature",
    },
    thermiaconst.ATTR_INPUT_CONDENSER_OUT_TEMPERATURE: {
        ATTR_LABEL: "Condenser Out Temperature",
    },
    thermiaconst.ATTR_INPUT_BRINE_IN_TEMPERATURE: {
        ATTR_LABEL: "Brine In Temperature",
    },
    thermiaconst.ATTR_INPUT_BRINE_OUT_TEMPERATURE: {
        ATTR_LABEL: "Brine Out Temperature",
    },
    thermiaconst.ATTR_INPUT_SYSTEM_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "System Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_OUTDOOR_TEMPERATURE: {
        ATTR_LABEL: "Outdoor Temperature",
    },
    thermiaconst.ATTR_INPUT_TAP_WATER_TOP_TEMPERATURE: {
        ATTR_LABEL: "Tap Water Top Temperature",
    },
    thermiaconst.ATTR_INPUT_TAP_WATER_LOWER_TEMPERATURE: {
        ATTR_LABEL: "Tap Water Lower Temperature",
    },
    thermiaconst.ATTR_INPUT_TAP_WATER_WEIGHTED_TEMPERATURE: {
        ATTR_LABEL: "Tap Water Weighted Temperature",
    },
    thermiaconst.ATTR_INPUT_SYSTEM_SUPPLY_LINE_CALCULATED_SET_POINT: {
        ATTR_LABEL: "System Supply Line Calculated Set Point",
    },
    thermiaconst.ATTR_INPUT_SELECTED_HEAT_CURVE: {
        ATTR_LABEL: "Selected Heat Curve",
    },
    thermiaconst.ATTR_INPUT_HEAT_CURVE_X_COORDINATE_1: {
        ATTR_LABEL: "Heat Curve X Coordinate 1",
    },
    thermiaconst.ATTR_INPUT_HEAT_CURVE_X_COORDINATE_2: {
        ATTR_LABEL: "Heat Curve X Coordinate 2",
    },
    thermiaconst.ATTR_INPUT_HEAT_CURVE_X_COORDINATE_3: {
        ATTR_LABEL: "Heat Curve X Coordinate 3",
    },
    thermiaconst.ATTR_INPUT_HEAT_CURVE_X_COORDINATE_4: {
        ATTR_LABEL: "Heat Curve X Coordinate 4",
    },
    thermiaconst.ATTR_INPUT_HEAT_CURVE_X_COORDINATE_5: {
        ATTR_LABEL: "Heat Curve X Coordinate 5",
    },
    thermiaconst.ATTR_INPUT_HEAT_CURVE_X_COORDINATE_6: {
        ATTR_LABEL: "Heat Curve X Coordinate 6",
    },
    thermiaconst.ATTR_INPUT_HEAT_CURVE_X_COORDINATE_7: {
        ATTR_LABEL: "Heat Curve X Coordinate 7",
    },
    thermiaconst.ATTR_INPUT_COOLING_SEASON_INTEGRAL_VALUE: {
        ATTR_LABEL: "Cooling Season Integral Value",
    },
    thermiaconst.ATTR_INPUT_CONDENSER_CIRCULATION_PUMP_SPEED: {
        ATTR_LABEL: "Condenser Circulation Pump Speed",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_1_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "Mix Valve 1 Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_BUFFER_TANK_TEMPERATURE: {
        ATTR_LABEL: "Buffer Tank Temperature",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_1_POSITION: {
        ATTR_LABEL: "Mix Valve 1 Position",
    },
    thermiaconst.ATTR_INPUT_BRINE_CIRCULATION_PUMP_SPEED: {
        ATTR_LABEL: "Brine Circulation Pump Speed",
    },
    thermiaconst.ATTR_INPUT_HGW_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "Hgw Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_HOT_WATER_DIRECTIONAL_VALVE_POSITION: {
        ATTR_LABEL: "Hot Water Directional Valve Position",
    },
    thermiaconst.ATTR_INPUT_COMPRESSOR_OPERATING_HOURS: {
        ATTR_LABEL: "Compressor Operating Hours",
    },
    thermiaconst.ATTR_INPUT_TAP_WATER_OPERATING_HOURS: {
        ATTR_LABEL: "Tap Water Operating Hours",
    },
    thermiaconst.ATTR_INPUT_EXTERNAL_ADDITIONAL_HEATER_OPERATING_HOURS: {
        ATTR_LABEL: "External Additional Heater Operating Hours",
    },
    thermiaconst.ATTR_INPUT_COMPRESSOR_SPEED_PERCENT: {
        ATTR_LABEL: "Compressor Speed Percent",
    },
    thermiaconst.ATTR_INPUT_SECOND_PRIORITISED_DEMAND: {
        ATTR_LABEL: "Second Prioritised Demand",
    },
    thermiaconst.ATTR_INPUT_THIRD_PRIORITISED_DEMAND: {
        ATTR_LABEL: "Third Prioritised Demand",
    },
    thermiaconst.ATTR_INPUT_SOFTWARE_VERSION_MAJOR: {
        ATTR_LABEL: "Software Version Major",
    },
    thermiaconst.ATTR_INPUT_SOFTWARE_VERSION_MINOR: {
        ATTR_LABEL: "Software Version Minor",
    },
    thermiaconst.ATTR_INPUT_SOFTWARE_VERSION_MICRO: {
        ATTR_LABEL: "Software Version Micro",
    },
    thermiaconst.ATTR_INPUT_COMPRESSOR_TEMPORARILY_BLOCKED: {
        ATTR_LABEL: "Compressor Temporarily Blocked",
    },
    thermiaconst.ATTR_INPUT_COMPRESSOR_CURRENT_GEAR: {
        ATTR_LABEL: "Compressor Current Gear",
    },
    thermiaconst.ATTR_INPUT_QUEUED_DEMAND_FIRST_PRIORITY: {
        ATTR_LABEL: "Queued Demand First Priority",
    },
    thermiaconst.ATTR_INPUT_QUEUED_DEMAND_SECOND_PRIORITY: {
        ATTR_LABEL: "Queued Demand Second Priority",
    },
    thermiaconst.ATTR_INPUT_QUEUED_DEMAND_THIRD_PRIORITY: {
        ATTR_LABEL: "Queued Demand Third Priority",
    },
    thermiaconst.ATTR_INPUT_QUEUED_DEMAND_FOURTH_PRIORITY: {
        ATTR_LABEL: "Queued Demand Fourth Priority",
    },
    thermiaconst.ATTR_INPUT_QUEUED_DEMAND_FIFTH_PRIORITY: {
        ATTR_LABEL: "Queued Demand Fifth Priority",
    },
    thermiaconst.ATTR_INPUT_INTERNAL_ADDITIONAL_HEATER_CURRENT_STEP: {
        ATTR_LABEL: "Internal Additional Heater Current Step",
    },
    thermiaconst.ATTR_INPUT_BUFFER_TANK_CHARGE_SET_POINT: {
        ATTR_LABEL: "Buffer Tank Charge Set Point",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L1_CURRENT: {
        ATTR_LABEL: "Electric Meter L1 Current",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L2_CURRENT: {
        ATTR_LABEL: "Electric Meter L2 Current",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L3_CURRENT: {
        ATTR_LABEL: "Electric Meter L3 Current",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L1_0_VOLTAGE: {
        ATTR_LABEL: "Electric Meter L1 0 Voltage",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L2_0_VOLTAGE: {
        ATTR_LABEL: "Electric Meter L2 0 Voltage",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L3_0_VOLTAGE: {
        ATTR_LABEL: "Electric Meter L3 0 Voltage",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L1_L2_VOLTAGE: {
        ATTR_LABEL: "Electric Meter L1 L2 Voltage",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L2_L3_VOLTAGE: {
        ATTR_LABEL: "Electric Meter L2 L3 Voltage",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L3_L1_VOLTAGE: {
        ATTR_LABEL: "Electric Meter L3 L1 Voltage",
    },
    # Inputs 157/158; kW per the display's daily COP (homelab exploration-8 round 10).
    thermiaconst.ATTR_INPUT_CURRENT_POWER_OUTPUT: {
        ATTR_LABEL: "Current Power Output",
        ATTR_DEFAULT_ENABLED: True,
    },
    thermiaconst.ATTR_INPUT_CURRENT_CONSUMED_POWER: {
        ATTR_LABEL: "Current Consumed Power",
        ATTR_DEFAULT_ENABLED: True,
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L1_POWER: {
        ATTR_LABEL: "Electric Meter L1 Power",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L2_POWER: {
        ATTR_LABEL: "Electric Meter L2 Power",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_L3_POWER: {
        ATTR_LABEL: "Electric Meter L3 Power",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_METER_VALUE: {
        ATTR_LABEL: "Electric Meter Meter Value",
    },
    thermiaconst.ATTR_INPUT_COMFORT_MODE: {
        ATTR_LABEL: "Comfort Mode",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_KWH_TOTAL: {
        ATTR_LABEL: "Electric Meter Kwh Total",
    },
    thermiaconst.ATTR_INPUT_WCS_VALVE_POSITION: {
        ATTR_LABEL: "WCS Valve Position",
    },
    thermiaconst.ATTR_INPUT_TWC_VALVE_POSITION: {
        ATTR_LABEL: "TWC Valve Position",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_2_POSITION: {
        ATTR_LABEL: "Mix Valve 2 Position",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_3_POSITION: {
        ATTR_LABEL: "Mix Valve 3 Position",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_4_POSITION: {
        ATTR_LABEL: "Mix Valve 4 Position",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_5_POSITION: {
        ATTR_LABEL: "Mix Valve 5 Position",
    },
    thermiaconst.ATTR_INPUT_DEW_POINT_ROOM: {
        ATTR_LABEL: "Dew Point Room",
    },
    thermiaconst.ATTR_INPUT_COOLING_SUPPLY_LINE_MIX_VALVE_POSITION: {
        ATTR_LABEL: "Cooling Supply Line Mix Valve Position",
    },
    thermiaconst.ATTR_INPUT_SURPLUS_HEAT_FAN_SPEED: {
        ATTR_LABEL: "Surplus Heat Fan Speed",
    },
    thermiaconst.ATTR_INPUT_POOL_SUPPLY_LINE_MIX_VALVE_POSITION: {
        ATTR_LABEL: "Pool Supply Line Mix Valve Position",
    },
    thermiaconst.ATTR_INPUT_TWC_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "TWC Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_TWC_RETURN_TEMPERATURE: {
        ATTR_LABEL: "TWC Return Temperature",
    },
    thermiaconst.ATTR_INPUT_WCS_RETURN_LINE_TEMPERATURE: {
        ATTR_LABEL: "WCS Return Line Temperature",
    },
    thermiaconst.ATTR_INPUT_TWC_END_TANK_TEMPERATURE: {
        ATTR_LABEL: "TWC End Tank Temperature",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_2_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "Mix Valve 2 Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_3_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "Mix Valve 3 Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_4_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "Mix Valve 4 Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_COOLING_CIRCUIT_RETURN_LINE_TEMPERATURE: {
        ATTR_LABEL: "Cooling Circuit Return Line Temperature",
    },
    thermiaconst.ATTR_INPUT_COOLING_TANK_TEMPERATURE: {
        ATTR_LABEL: "Cooling Tank Temperature",
    },
    thermiaconst.ATTR_INPUT_COOLING_TANK_RETURN_LINE_TEMPERATURE: {
        ATTR_LABEL: "Cooling Tank Return Line Temperature",
    },
    thermiaconst.ATTR_INPUT_COOLING_CIRCUIT_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "Cooling Circuit Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_5_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "Mix Valve 5 Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_2_RETURN_LINE_TEMPERATURE: {
        ATTR_LABEL: "Mix Valve 2 Return Line Temperature",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_3_RETURN_LINE_TEMPERATURE: {
        ATTR_LABEL: "Mix Valve 3 Return Line Temperature",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_4_RETURN_LINE_TEMPERATURE: {
        ATTR_LABEL: "Mix Valve 4 Return Line Temperature",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_5_RETURN_LINE_TEMPERATURE: {
        ATTR_LABEL: "Mix Valve 5 Return Line Temperature",
    },
    thermiaconst.ATTR_INPUT_SURPLUS_HEAT_RETURN_LINE_TEMPERATURE: {
        ATTR_LABEL: "Surplus Heat Return Line Temperature",
    },
    thermiaconst.ATTR_INPUT_SURPLUS_HEAT_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "Surplus Heat Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_POOL_SUPPLY_LINE_TEMPERATURE: {
        ATTR_LABEL: "Pool Supply Line Temperature",
    },
    thermiaconst.ATTR_INPUT_POOL_RETURN_LINE_TEMPERATURE: {
        ATTR_LABEL: "Pool Return Line Temperature",
    },
    thermiaconst.ATTR_INPUT_ROOM_TEMPERATURE_SENSOR: {
        ATTR_LABEL: "Room Temperature Sensor",
    },
    thermiaconst.ATTR_INPUT_BUBBLE_POINT: {
        ATTR_LABEL: "Bubble Point",
    },
    thermiaconst.ATTR_INPUT_DEW_POINT: {
        ATTR_LABEL: "Dew Point",
    },
    thermiaconst.ATTR_INPUT_SUPERHEAT_TEMPERATURE: {
        ATTR_LABEL: "Superheat Temperature",
    },
    thermiaconst.ATTR_INPUT_SUB_COOLING_TEMPERATURE: {
        ATTR_LABEL: "Sub Cooling Temperature",
    },
    thermiaconst.ATTR_INPUT_LOW_PRESSURE_SIDE: {
        ATTR_LABEL: "Low Pressure Side",
    },
    thermiaconst.ATTR_INPUT_HIGH_PRESSURE_SIDE: {
        ATTR_LABEL: "High Pressure Side",
    },
    thermiaconst.ATTR_INPUT_LIQUID_LINE_TEMPERATURE: {
        ATTR_LABEL: "Liquid Line Temperature",
    },
    thermiaconst.ATTR_INPUT_SUCTION_GAS_TEMPERATURE: {
        ATTR_LABEL: "Suction Gas Temperature",
    },
    thermiaconst.ATTR_INPUT_HEATING_SEASON_INTEGRAL_VALUE: {
        ATTR_LABEL: "Heating Season Integral Value",
    },
    thermiaconst.ATTR_INPUT_P_VALUE_FOR_GEAR_SHIFTING_AND_DEMAND_CALCULATION: {
        ATTR_LABEL: "P Value For Gear Shifting And Demand Calculation",
    },
    thermiaconst.ATTR_INPUT_I_VALUE_FOR_GEAR_SHIFTING_AND_DEMAND_CALCULATION: {
        ATTR_LABEL: "I Value For Gear Shifting And Demand Calculation",
    },
    thermiaconst.ATTR_INPUT_D_VALUE_FOR_GEAR_SHIFTING_AND_DEMAND_CALCULATION: {
        ATTR_LABEL: "D Value For Gear Shifting And Demand Calculation",
    },
    thermiaconst.ATTR_INPUT_I_VALUE_FOR_COMPRESSOR_ON_OFF_BUFFER_TANK: {
        ATTR_LABEL: "I Value For Compressor On Off Buffer Tank",
    },
    thermiaconst.ATTR_INPUT_P_VALUE_FOR_COMPRESSOR_ON_OFF_BUFFER_TANK: {
        ATTR_LABEL: "P Value For Compressor On Off Buffer Tank",
    },
    thermiaconst.ATTR_INPUT_MIX_VALVE_COOLING_OPENING_DEGREE: {
        ATTR_LABEL: "Mix Valve Cooling Opening Degree",
    },
    thermiaconst.ATTR_INPUT_DESIRED_GEAR_FOR_TAP_WATER: {
        ATTR_LABEL: "Desired Gear For Tap Water",
    },
    thermiaconst.ATTR_INPUT_DESIRED_GEAR_FOR_HEATING: {
        ATTR_LABEL: "Desired Gear For Heating",
    },
    thermiaconst.ATTR_INPUT_DESIRED_GEAR_FOR_COOLING: {
        ATTR_LABEL: "Desired Gear For Cooling",
    },
    thermiaconst.ATTR_INPUT_DESIRED_GEAR_FOR_POOL: {
        ATTR_LABEL: "Desired Gear For Pool",
    },
    thermiaconst.ATTR_INPUT_NUMBER_OF_AVAILABLE_SECONDARIES_GENESIS: {
        ATTR_LABEL: "Number Of Available Secondaries Genesis",
    },
    thermiaconst.ATTR_INPUT_NUMBER_OF_AVAILABLE_SECONDARIES_LEGACY: {
        ATTR_LABEL: "Number Of Available Secondaries Legacy",
    },
    thermiaconst.ATTR_INPUT_TOTAL_DISTRIBUTED_GEARS_TO_ALL_UNITS: {
        ATTR_LABEL: "Total Distributed Gears To All Units",
    },
    thermiaconst.ATTR_INPUT_MAXIMUM_GEAR_OUT_OF_ALL_THE_CURRENTLY_REQUESTED_GEARS: {
        ATTR_LABEL: "Maximum Gear Out Of All The Currently Requested Gears",
    },
    thermiaconst.ATTR_INPUT_DESIRED_TEMPERATURE_DISTRIBUTION_CIRCUIT_MIX_VALVE_1: {
        ATTR_LABEL: "Desired Temperature Distribution Circuit Mix Valve 1",
    },
    thermiaconst.ATTR_INPUT_DESIRED_TEMPERATURE_DISTRIBUTION_CIRCUIT_MIX_VALVE_2: {
        ATTR_LABEL: "Desired Temperature Distribution Circuit Mix Valve 2",
    },
    thermiaconst.ATTR_INPUT_DESIRED_TEMPERATURE_DISTRIBUTION_CIRCUIT_MIX_VALVE_3: {
        ATTR_LABEL: "Desired Temperature Distribution Circuit Mix Valve 3",
    },
    thermiaconst.ATTR_INPUT_DESIRED_TEMPERATURE_DISTRIBUTION_CIRCUIT_MIX_VALVE_4: {
        ATTR_LABEL: "Desired Temperature Distribution Circuit Mix Valve 4",
    },
    thermiaconst.ATTR_INPUT_DESIRED_TEMPERATURE_DISTRIBUTION_CIRCUIT_MIX_VALVE_5: {
        ATTR_LABEL: "Desired Temperature Distribution Circuit Mix Valve 5",
    },
    thermiaconst.ATTR_INPUT_DISCONNECT_HOT_GAS_END_TANK: {
        ATTR_LABEL: "Disconnect Hot Gas End Tank",
    },
    thermiaconst.ATTR_INPUT_LEGACY_HEAT_PUMP_COMPRESSOR_RUNNING: {
        ATTR_LABEL: "Legacy Heat Pump Compressor Running",
    },
    thermiaconst.ATTR_INPUT_LEGACY_HEAT_PUMP_REPORTING_ALARM: {
        ATTR_LABEL: "Legacy Heat Pump Reporting Alarm",
    },
    thermiaconst.ATTR_INPUT_LEGACY_HEAT_PUMP_START_SIGNAL: {
        ATTR_LABEL: "Legacy Heat Pump Start Signal",
    },
    thermiaconst.ATTR_INPUT_LEGACY_HEAT_PUMP_TAP_WATER_SIGNAL: {
        ATTR_LABEL: "Legacy Heat Pump Tap Water Signal",
    },
    thermiaconst.ATTR_INPUT_PRIMARY_UNIT_ALARM_COMBINED_OUTPUT_OF_ALL_CLASS_D_ALARMS: {
        ATTR_LABEL: "Primary Unit Alarm Combined Output Of All Class D Alarms",
    },
    thermiaconst.ATTR_INPUT_PRIMARY_UNIT_ALARM_PRIMARY_UNIT_HAS_LOST_COMMUNICATION: {
        ATTR_LABEL: "Primary Unit Alarm Primary Unit Has Lost Communication",
    },
    thermiaconst.ATTR_INPUT_PRIMARY_UNIT_ALARM_CLASS_A_ALARM_DETECTED_ON_THE_GENESIS_SECONDARY: {
        ATTR_LABEL: "Primary Unit Alarm Class A Alarm Detected On The Genesis Secondary",
    },
    thermiaconst.ATTR_INPUT_PRIMARY_UNIT_ALARM_CLASS_B_ALARM_DETECTED_ON_THE_GENESIS_SECONDARY: {
        ATTR_LABEL: "Primary Unit Alarm Class B Alarm Detected On The Genesis Secondary",
    },
    thermiaconst.ATTR_INPUT_PRIMARY_UNIT_ALARM_COMBINED_OUTPUT_OF_ALL_CLASS_E_ALARMS: {
        ATTR_LABEL: "Primary Unit Alarm Combined Output Of All Class E Alarms",
    },
    thermiaconst.ATTR_INPUT_PRIMARY_UNIT_ALARM_GENERAL_LEGACY_HEAT_PUMP_ALARM: {
        ATTR_LABEL: "Primary Unit Alarm General Legacy Heat Pump Alarm",
    },
    thermiaconst.ATTR_INPUT_PRIMARY_UNIT_ALARM_PRIMARY_UNIT_CAN_NOT_COMMUNICATE_WITH_EXPANSION: {
        ATTR_LABEL: "Primary Unit Alarm Primary Unit Can Not Communicate With Expansion",
    },
}



# DHF-REQ: genesis-wp-ha/requirement-17
# These registers have a purpose outside the register entity platforms.
REGISTER_EXCLUSIONS = {
    thermiaconst.ATTR_COIL_RESET_ALL_ALARMS: "Action command, not a readable state",
    thermiaconst.ATTR_INPUT_CONTROL_SOFTWARE_VERSION_MAJOR: "Controller software version in device info",
    thermiaconst.ATTR_INPUT_CONTROL_SOFTWARE_VERSION_MINOR: "Controller software version in device info",
    thermiaconst.ATTR_INPUT_CONTROL_SOFTWARE_VERSION_MICRO: "Controller software version in device info",
}

# DHF-REQ: genesis-wp-ha/requirement-9
# DHF-REQ: genesis-wp-ha/requirement-17
# Explicit exceptions to library metadata; remove as library corrections land.
REGISTER_OVERRIDES = {
    thermiaconst.ATTR_HOLDING_COMFORT_WHEEL_SETTING: {
        "unit": "°C",
        "kind": "temperature",
        "reason": "Absolute room set point; library temperature_delta misclassification pending library fix",
    },
    thermiaconst.ATTR_INPUT_ELECTRIC_METER_KWH_TOTAL: {
        "unit": "kWh",
        "kind": "energy",
        "reason": "Energy total; library count metadata pending genesis-wp issue-28",
    },
}
