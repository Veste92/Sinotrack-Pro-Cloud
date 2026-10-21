"""SinoTrack Pro Cloud integration."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SinoTrackApi
from .const import (
    CONF_DEVICE_ID, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_SERVER,
    CONF_STALE_AFTER, CONF_USERNAME, DEFAULT_SCAN_INTERVAL,
    DEFAULT_STALE_AFTER, DOMAIN, MAX_SCAN_INTERVAL, MAX_STALE_AFTER,
    MIN_SCAN_INTERVAL, MIN_STALE_AFTER,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.DEVICE_TRACKER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = SinoTrackApi(
        entry.data[CONF_SERVER], entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD], session=async_get_clientsession(hass),
    )
    scan = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    stale_after = int(entry.options.get(CONF_STALE_AFTER, DEFAULT_STALE_AFTER))
    scan = max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, scan))
    stale_after = max(MIN_STALE_AFTER, min(MAX_STALE_AFTER, stale_after))

    async def _async_update():
        try:
            data = dict(await api.async_get_position(entry.data[CONF_DEVICE_ID]))
            age = api.gps_fix_age_seconds(data.get("timestamp"))
            data["gps_fix_age_seconds"] = age
            data["gps_is_stale"] = age is None or age > stale_after
            data["gps_stale_after_seconds"] = stale_after
            return data
        except Exception as err:
            _LOGGER.debug("SinoTrack update failed (%s)", type(err).__name__)
            raise UpdateFailed(
                f"SinoTrack cloud request failed: {type(err).__name__}"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass, _LOGGER, name="SinoTrack Pro", update_method=_async_update,
        update_interval=timedelta(seconds=scan),
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        await api.async_close()
        raise ConfigEntryNotReady("Unable to retrieve SinoTrack data") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator, "api": api,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["api"].async_close()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
