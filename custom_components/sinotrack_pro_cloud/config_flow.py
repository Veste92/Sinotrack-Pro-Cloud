"""Config flow for SinoTrack Pro Cloud."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import SinoTrackApi
from .const import (
    DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_DEVICE_ID, CONF_SERVER,
    CONF_SCAN_INTERVAL, CONF_STALE_AFTER, DEFAULT_SERVER, DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_AFTER, MIN_SCAN_INTERVAL, MAX_SCAN_INTERVAL,
    MIN_STALE_AFTER, MAX_STALE_AFTER,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up SinoTrack credentials."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            server = user_input[CONF_SERVER].rstrip("/")
            api = SinoTrackApi(
                server, user_input[CONF_USERNAME], user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await api.async_get_position(user_input[CONF_DEVICE_ID])
            except Exception as err:
                _LOGGER.warning("SinoTrack setup failed (%s)", type(err).__name__)
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{server}:{user_input[CONF_USERNAME]}:{user_input[CONF_DEVICE_ID]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"SinoTrack {user_input[CONF_DEVICE_ID]}",
                    data={**user_input, CONF_SERVER: server},
                )
        schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_SERVER, default=DEFAULT_SERVER): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for polling and GPS freshness."""
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=int(self.config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ))): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
            vol.Required(CONF_STALE_AFTER, default=int(self.config_entry.options.get(
                CONF_STALE_AFTER, DEFAULT_STALE_AFTER
            ))): vol.All(vol.Coerce(int), vol.Range(min=MIN_STALE_AFTER, max=MAX_STALE_AFTER)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
