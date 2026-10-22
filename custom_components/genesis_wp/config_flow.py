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

    def _schema(self, defaults):
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=defaults[CONF_PORT]): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(CONF_UNIT, default=defaults[CONF_UNIT]): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=255)
                ),
                vol.Required(CONF_MODEL, default=defaults[CONF_MODEL]): selector(
                    {
                        "select": {
                            "options": [
                                {"value": kind, "label": name}
                                for kind, name in MODEL_NAMES.items()
                            ],
                        }
                    }
                ),
            }
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST].lower()}:{user_input[CONF_PORT]}:{user_input[CONF_UNIT]}"
            )
            self._abort_if_unique_id_configured()
            try:
                await self._validate_input(user_input)
            except (ThermiaException, ValueError) as err:
                # Exception text may carry the host, which is topology: log the type only.
                _LOGGER.info("Heat pump did not answer: %s", type(err).__name__)
                errors["base"] = "cannot_connect"
            else:
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
