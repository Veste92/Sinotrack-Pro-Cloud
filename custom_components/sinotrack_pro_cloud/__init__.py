"""SinoTrack Pro cloud integration."""
from datetime import timedelta
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICE_ID,
    CONF_SERVER,
    SCAN_INTERVAL,
)
from .api import SinoTrackApi
_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.DEVICE_TRACKER, Platform.SENSOR]
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    api = SinoTrackApi(
        entry.data[CONF_SERVER],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    async def _async_update():
        try:
            device_id = entry.data[CONF_DEVICE_ID]
            # Diagnostic request to test the vehicle information command.
            try:
                await api.async_get_car_info(device_id)
            except Exception:
                _LOGGER.exception(
                    "SinoTrack car-info diagnostic request failed"
                )
            # Keep the existing GPS position request.
            return await api.async_get_position(device_id)
        except Exception as err:
            raise UpdateFailed(
                f"SinoTrack cloud request failed: {err}"
            ) from err
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="SinoTrack Pro",
        update_method=_async_update,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }
    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )
    return True
async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    ):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["api"].async_close()
    return unload_ok