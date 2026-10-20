"""Config flow for SinoTrack Pro Cloud."""
import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, CONF_SERVER, DEFAULT_SERVER
from .api import SinoTrackApi
_LOGGER = logging.getLogger(__name__)

class CannotConnect(HomeAssistantError):
    """Cannot connect or credentials rejected."""

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            server = user_input[CONF_SERVER].rstrip("/")
            try:
                api = SinoTrackApi(server, user_input[CONF_USERNAME], user_input[CONF_PASSWORD],
                                   session=async_get_clientsession(self.hass))
                await api.async_get_position(user_input[CONF_DEVICE_ID])
            except Exception as err:
                _LOGGER.exception("SinoTrack Pro setup failed (credentials omitted): %s", type(err).__name__)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"{server}:{user_input[CONF_USERNAME]}:{user_input[CONF_DEVICE_ID]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"SinoTrack {user_input[CONF_DEVICE_ID]}", data={
                    **user_input, CONF_SERVER: server
                })
        schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_DEVICE_ID, default="9171012315"): str,
            vol.Required(CONF_SERVER, default=DEFAULT_SERVER): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
