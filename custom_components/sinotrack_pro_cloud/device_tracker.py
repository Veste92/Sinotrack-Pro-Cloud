"""SinoTrack cloud device tracker."""
from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_DEVICE_ID


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SinoTrackTracker(hass.data[DOMAIN][entry.entry_id]["coordinator"], entry)])


class SinoTrackTracker(CoordinatorEntity, TrackerEntity):
    """Represent the configured tracker."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:car"
    _attr_should_poll = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{entry.entry_id}_{self._device_id}_tracker"
        self._attr_name = f"SinoTrack {self._device_id}"

    @property
    def source_type(self):
        return SourceType.GPS

    @property
    def latitude(self):
        return (self.coordinator.data or {}).get("latitude")

    @property
    def longitude(self):
        return (self.coordinator.data or {}).get("longitude")

    @property
    def location_accuracy(self):
        return 20

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "speed_kmh": data.get("speed"), "heading": data.get("heading"),
            "device_id": self._device_id, "timestamp": data.get("timestamp"),
            "last_gps_update": data.get("last_gps_update"),
            "gps_fix_age_seconds": data.get("gps_fix_age_seconds"),
            "gps_is_stale": data.get("gps_is_stale"),
            "gps_stale_after_seconds": data.get("gps_stale_after_seconds"),
        }
