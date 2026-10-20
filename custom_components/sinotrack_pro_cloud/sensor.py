
"""SinoTrack cloud sensors."""

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfSpeed, UnitOfLength
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_DEVICE_ID


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    sensors = [
        SinoTrackSensor(
            coordinator, entry, "speed", "Speed",
            UnitOfSpeed.KILOMETERS_PER_HOUR, "mdi:speedometer"
        ),
        SinoTrackSensor(
            coordinator, entry, "latitude", "Latitude",
            None, "mdi:latitude"
        ),
        SinoTrackSensor(
            coordinator, entry, "longitude", "Longitude",
            None, "mdi:longitude"
        ),
        SinoTrackSensor(
            coordinator, entry, "heading", "Heading",
            "°", "mdi:compass"
        ),
        SinoTrackSensor(
            coordinator, entry, "timestamp", "Last GPS timestamp",
            None, "mdi:clock-outline"
        ),
        SinoTrackSensor(
            coordinator, entry, "odometer_miles", "Total Mileage",
            UnitOfLength.MILES, "mdi:counter"
        ),
        SinoTrackSensor(
            coordinator, entry, "start_mileage", "Initial Mileage (diagnostic)",
            None, "mdi:counter"
        ),
    ]

    async_add_entities(sensors)


class SinoTrackSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, entry, key, label, unit, icon):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = label
        self._attr_unique_id = (
            f"{entry.entry_id}_{entry.data[CONF_DEVICE_ID]}_{key}"
        )
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

        if key in ("latitude", "longitude"):
            self._attr_suggested_display_precision = 6

        if key == "speed":
            self._attr_state_class = SensorStateClass.MEASUREMENT

        elif key == "odometer_miles":
            self._attr_device_class = SensorDeviceClass.DISTANCE
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None

        return self.coordinator.data.get(self.key)
