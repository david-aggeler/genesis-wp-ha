"""Config flow for genesis_wp heat pumps."""
import logging

import voluptuous as vol
from genesis_wp import ThermiaException
from genesis_wp.capabilities import ABSENT
from genesis_wp.capabilities import CAPABILITY_NAMES
from genesis_wp.capabilities import CAPABILITY_RULES
from genesis_wp.capabilities import PRESENT
from genesis_wp.capabilities import gated_registers
from genesis_wp.const import MODEL_NAMES
from genesis_wp.emulator import get_profile
from genesis_wp.emulator import packaged_profiles
from genesis_wp.emulator.capabilities import CapabilityError
from genesis_wp.emulator.capabilities import selection_overrides
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import NumberSelector
from homeassistant.helpers.selector import NumberSelectorConfig
from homeassistant.helpers.selector import NumberSelectorMode
from homeassistant.helpers.selector import selector

from . import create_client
from . import detect_capabilities
from .const import CONF_ADVANCED
from .const import CONF_CAPABILITIES
from .const import CONF_MODE
from .const import CONF_MODEL
from .const import CONF_PROFILE
from .const import CONF_UNIT
from .const import DEFAULT_MODEL
from .const import DEFAULT_PORT
from .const import DEFAULT_UNIT
from .const import DOMAIN
from .const import HEATPUMP_SENSOR
from .const import MODE_EMULATED
from .const import MODULE_AUTOMATIC
from .const import MODULE_INSTALLED
from .const import MODULE_NOT_INSTALLED

_LOGGER = logging.getLogger(__name__)


MODULE_STATES = {MODULE_INSTALLED: PRESENT, MODULE_NOT_INSTALLED: ABSENT}


def model_capabilities(kind) -> list[str]:
    """Capabilities that gate registers on model ``kind``: the modules the options step offers."""
    return [rule.name for rule in CAPABILITY_RULES if gated_registers(rule, kind)]


def switchable_capabilities(profile) -> list[str]:
    """Capabilities the emulator can present both on and off for ``profile``; the library decides."""
    names = []
    for name in CAPABILITY_NAMES:
        try:
            selection_overrides(profile, {name: True})
            selection_overrides(profile, {name: False})
        except CapabilityError:
            continue
        names.append(name)
    return names


class GenesisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a genesis_wp heat pump."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Module choices for an existing entry (requirement-14)."""
        return GenesisOptionsFlow()

    def __init__(self):
        """Initialize; the emulated path keeps the chosen profile and its detected defaults between steps."""
        self._profile = None
        self._module_defaults: dict[str, bool] = {}

    async def _validate_input(self, data):
        """Read one register to prove the device answers; never writes."""
        thermia = create_client(data)
        try:
            await thermia.async_update(only_registers=[HEATPUMP_SENSOR])
        finally:
            await thermia.close()
        if HEATPUMP_SENSOR not in thermia.data:
            raise ThermiaException("no data")

    @staticmethod
    def _connection(data):
        """The connection data that identifies a heat pump; the device has no serial or MAC to use."""
        return {key: data.get(key) for key in (CONF_HOST, CONF_PORT, CONF_UNIT)}

    async def _try_connect(self, data, errors):
        try:
            await self._validate_input(data)
        except (ThermiaException, ValueError) as err:
            # Exception text may carry the host, which is topology: log the type only.
            _LOGGER.info("Heat pump did not answer: %s", type(err).__name__)
            errors["base"] = "cannot_connect"
            return False
        return True

    @staticmethod
    def _flatten(user_input):
        """Form input to entry data: lift port out of its section as an int; the unit is always 1."""
        advanced = user_input[CONF_ADVANCED]
        data = {key: value for key, value in user_input.items() if key != CONF_ADVANCED}
        data[CONF_HOST] = data[CONF_HOST].strip()
        data[CONF_PORT] = int(advanced[CONF_PORT])
        data[CONF_UNIT] = DEFAULT_UNIT  # the WPM-G serves Modbus TCP itself: no gateway, no other unit
        return data

    @staticmethod
    def _number_box(low, high):
        return NumberSelector(
            NumberSelectorConfig(min=low, max=high, step=1, mode=NumberSelectorMode.BOX)
        )

    @staticmethod
    def _model_selector():
        return selector(
            {
                "select": {
                    "options": [
                        {"value": kind, "label": name}
                        for kind, name in MODEL_NAMES.items()
                    ],
                }
            }
        )

    def _schema(self, defaults, with_model=True):
        # Port sits in a collapsed section: nearly every install keeps 502.
        advanced = vol.Schema(
            {
                vol.Required(CONF_PORT, default=defaults[CONF_PORT]): self._number_box(1, 65535),
            }
        )
        fields = {
            vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
            vol.Required(CONF_ADVANCED): section(advanced, {"collapsed": True}),
        }
        if with_model:
            fields[vol.Required(CONF_MODEL, default=defaults[CONF_MODEL])] = self._model_selector()
        return vol.Schema(fields)

    async def async_step_user(self, user_input=None):
        """Choose between a real heat pump and an emulated one."""
        return self.async_show_menu(step_id="user", menu_options=["real", MODE_EMULATED])

    async def async_step_emulated(self, user_input=None):
        """Pick a packaged firmware profile; the integration runs it in-process on loopback."""
        if user_input is not None:
            self._profile = get_profile(user_input[CONF_PROFILE])
            return await self.async_step_modules()

        profiles = packaged_profiles()
        schema = vol.Schema(
            {
                vol.Required(CONF_PROFILE, default=profiles[-1]): selector(
                    {"select": {"options": [{"value": p, "label": p} for p in profiles]}}
                ),
            }
        )
        return self.async_show_form(step_id=MODE_EMULATED, data_schema=schema)

    async def async_step_modules(self, user_input=None):
        """Switch the profile's plant modules on or off; defaults are what the recording contains (requirement-13)."""
        profile = self._profile
        if user_input is None:
            detected = await detect_capabilities(profile)
            self._module_defaults = {
                name: detected.get(name) == PRESENT for name in switchable_capabilities(profile)
            }
            schema = vol.Schema(
                {vol.Required(name, default=on): bool for name, on in self._module_defaults.items()}
            )
            return self.async_show_form(step_id="modules", data_schema=schema)

        # Only the choices that differ from the recording: the profile stays the baseline.
        capabilities = {
            name: user_input[name]
            for name, on in self._module_defaults.items()
            if user_input.get(name, on) != on
        }
        data = {CONF_MODE: MODE_EMULATED, CONF_PROFILE: profile.name, CONF_MODEL: profile.model}
        if capabilities:
            data[CONF_CAPABILITIES] = capabilities
        self._async_abort_entries_match(data)
        return self.async_create_entry(title=f"{MODEL_NAMES[profile.model]} (emulated)", data=data)

    async def async_step_real(self, user_input=None):
        """Connect to a heat pump by host."""
        errors = {}
        if user_input is not None:
            user_input = self._flatten(user_input)
            # No unique_id: HA forbids host-derived ones, so duplicates are found by data match.
            self._async_abort_entries_match(self._connection(user_input))
            if await self._try_connect(user_input, errors):
                return self.async_create_entry(
                    title=MODEL_NAMES[user_input[CONF_MODEL]], data=user_input
                )

        defaults = user_input or {
            CONF_HOST: "",
            CONF_PORT: DEFAULT_PORT,
            CONF_UNIT: DEFAULT_UNIT,
            CONF_MODEL: DEFAULT_MODEL,
        }
        return self.async_show_form(
            step_id="real", data_schema=self._schema(defaults), errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Move an entry to a new host or port; the entry, its unit and its entities stay."""
        entry = self._get_reconfigure_entry()
        if entry.data.get(CONF_MODE) == MODE_EMULATED:
            return self.async_abort(reason="emulated_not_reconfigurable")
        errors = {}
        if user_input is not None:
            user_input = {**self._flatten(user_input), CONF_UNIT: entry.data[CONF_UNIT]}
            connection = self._connection(user_input)
            for other in self._async_current_entries(include_ignore=False):
                if other.entry_id != entry.entry_id and self._connection(other.data) == connection:
                    return self.async_abort(reason="already_configured")
            data = {**entry.data, **connection}
            if await self._try_connect(data, errors):
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema(user_input or entry.data, with_model=False),
            errors=errors,
        )


class GenesisOptionsFlow(config_entries.OptionsFlowWithReload):
    """Per module: automatic follows the library's detection, the others override it (requirement-14)."""

    async def async_step_init(self, user_input=None):
        """One select per module of the entry's model; only non-automatic choices are stored."""
        names = model_capabilities(self.config_entry.data[CONF_MODEL])
        if user_input is not None:
            return self.async_create_entry(
                data={
                    name: MODULE_STATES[user_input[name]]
                    for name in names
                    if user_input.get(name, MODULE_AUTOMATIC) in MODULE_STATES
                }
            )

        chosen = {state: choice for choice, state in MODULE_STATES.items()}
        options = self.config_entry.options
        module = selector(
            {
                "select": {
                    "options": [MODULE_AUTOMATIC, MODULE_INSTALLED, MODULE_NOT_INSTALLED],
                    "translation_key": "module",
                }
            }
        )
        schema = vol.Schema(
            {
                vol.Required(name, default=chosen.get(options.get(name), MODULE_AUTOMATIC)): module
                for name in names
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, description_placeholders={"detected": self._detected(names)}
        )

    def _detected(self, names) -> str:
        """What the running entry reports per module, so the user sees what automatic means today."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if coordinator is None:
            return "-"
        capabilities = coordinator.thermia.capabilities
        lines = []
        for name in names:
            cap = capabilities.get(name)
            if cap is not None:
                lines.append(f"{name}: {cap.state}{' (set here)' if cap.overridden else ''}")
        return ", ".join(lines) or "-"
