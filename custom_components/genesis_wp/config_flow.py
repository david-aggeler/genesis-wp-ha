"""Config flow for genesis_wp heat pumps."""
import logging

import voluptuous as vol
from genesis_wp import ThermiaException
from genesis_wp.const import MODEL_NAMES
from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PORT
from homeassistant.helpers.selector import selector

from . import create_client
from .const import CONF_MODEL
from .const import CONF_UNIT
from .const import DEFAULT_MODEL
from .const import DEFAULT_PORT
from .const import DEFAULT_UNIT
from .const import DOMAIN
from .const import HEATPUMP_SENSOR

_LOGGER = logging.getLogger(__name__)


class GenesisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a genesis_wp heat pump."""

    VERSION = 1

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
        return {key: data[key] for key in (CONF_HOST, CONF_PORT, CONF_UNIT)}

    async def _try_connect(self, data, errors):
        try:
            await self._validate_input(data)
        except (ThermiaException, ValueError) as err:
            # Exception text may carry the host, which is topology: log the type only.
            _LOGGER.info("Heat pump did not answer: %s", type(err).__name__)
            errors["base"] = "cannot_connect"
            return False
        return True

    def _schema(self, defaults, with_model=True):
        fields = {
            vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
            vol.Required(CONF_PORT, default=defaults[CONF_PORT]): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_UNIT, default=defaults[CONF_UNIT]): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        }
        if with_model:
            fields[vol.Required(CONF_MODEL, default=defaults[CONF_MODEL])] = selector(
                {
                    "select": {
                        "options": [
                            {"value": kind, "label": name}
                            for kind, name in MODEL_NAMES.items()
                        ],
                    }
                }
            )
        return vol.Schema(fields)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
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
            step_id="user", data_schema=self._schema(defaults), errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Move an entry to a new host, port or unit; the entry and its entities stay."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
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
