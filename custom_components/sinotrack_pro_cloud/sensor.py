"""SinoTrack cloud sensors."""
from datetime import datetime
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfLength, UnitOfSpeed
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_DEVICE_ID


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    sensors = [
        ("speed", "Speed", UnitOfSpeed.KILOMETERS_PER_HOUR, "mdi:speedometer"),
        ("latitude", "Latitude", None, "mdi:latitude"),
        ("longitude", "Longitude", None, "mdi:longitude"),
        ("heading", "Heading", "°", "mdi:compass"),
        ("timestamp", "Last GPS timestamp", None, "mdi:clock-outline"),
        ("odometer_miles", "Total Mileage", UnitOfLength.MILES, "mdi:counter"),
        ("odometer_km", "Total Mileage", UnitOfLength.KILOMETERS, "mdi:counter"),
        ("last_gps_update", "Last GPS Update", None, "mdi:clock-check-outline"),
        ("gps_fix_age_seconds", "GPS Fix Age", "s", "mdi:timer-sand"),
        ("gps_is_stale", "GPS Location Freshness", None, "mdi:map-marker-alert-outline"),
    ]
    async_add_entities([SinoTrackSensor(coordinator, entry, *item) for item in sensors])


class SinoTrackSensor(CoordinatorEntity, SensorEntity):
    """Represent one coordinator value."""
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, entry, key, label, unit, icon):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = label
        self._attr_unique_id = f"{entry.entry_id}_{entry.data[CONF_DEVICE_ID]}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        if key in ("latitude", "longitude"):
            self._attr_suggested_display_precision = 6
        if key == "speed":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key in ("odometer_miles", "odometer_km"):
            self._attr_device_class = SensorDeviceClass.DISTANCE
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif key == "gps_fix_age_seconds":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif key == "last_gps_update":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif key == "gps_is_stale":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ["fresh", "stale", "unknown"]

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        value = data.get(self.key)
        if self.key == "gps_is_stale":
            return "unknown" if value is None else ("stale" if value else "fresh")
        if self.key == "last_gps_update" and value:
            try:
                parsed = datetime.fromisoformat(value)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=__import__("datetime").timezone.utc)
            except (TypeError, ValueError):
                return None
        return value
