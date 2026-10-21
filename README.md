# SinoTrack Pro Cloud — v1.3.0

Custom Home Assistant integration for compatible SinoTrack GPS trackers.

## Phase 1 and 2 changes
- Reuses Home Assistant's managed HTTP session.
- Removes the separate diagnostic car-info call from every refresh.
- Caches initial mileage for ten minutes to reduce cloud requests.
- Implements the options flow for polling interval and GPS stale threshold.
- Exposes last GPS update, GPS fix age and fresh/stale status.
- Keeps unavailable mileage as unknown rather than silently replacing it with zero.
- Adds a kilometre odometer while retaining the existing miles sensor.
- Avoids logging response bodies or credentials on API errors.

## Install with HACS
Add `https://github.com/Veste92/Sinotrack-Pro-Cloud` as a custom Integration repository, download it, restart Home Assistant, then add SinoTrack Pro Cloud from Settings → Devices & services.

## Options
Polling interval: 30–3600 seconds (default 30).
GPS stale threshold: 60–86400 seconds (default 900 seconds / 15 minutes).

A stale status means the timestamp reported by SinoTrack is older than the selected threshold or could not be parsed. A tracker may remain online while its GPS fix is stale.

**Validation:** Python syntax is checked locally; live Home Assistant and SinoTrack API behaviour has not been tested. Confirm timestamps and odometer values against the SinoTrack portal before relying on them. This is a community integration, not an official SinoTrack product.
