"""Async client for the SinoTrack web API."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import random
import time
import aiohttp

ROW = "\x11"
TABLE = "\x1b"
KM_PER_MILE = 1.609344


class SinoTrackApi:
    """SinoTrack API client."""

    def __init__(self, server, username, password, session=None):
        self.server = server.rstrip("/")
        self.username = username
        self.password = password
        self._session = session
        self._owns_session = session is None
        self._logged_in = False
        self._initial_mileage_cache = {}

    async def async_close(self):
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None

    def _b64(self, value):
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    def _app_id(self):
        host = self.server.lower().replace("http://", "").replace("https://", "")
        while len(host) % 3:
            host += "/"
        return self._b64(host)

    def _encode_command(self, cmd, data, fields=""):
        token_raw = cmd + ROW + data + ROW + fields + ROW + TABLE
        seed = "MGTS_" + str(int(random.random() * 10**14)).zfill(14)
        while len(token_raw) % 3:
            token_raw += ("MGTS_" + str(int(random.random() * 10**14)).zfill(14))[7]
        token = self._b64(token_raw)
        timestamp = str(int(time.time() * 1000))
        rand = seed.replace("MGTS_", "")
        signature = hashlib.md5(
            (timestamp + rand + self.username + self._app_id() + token).encode()
        ).hexdigest()
        return {"strAppID": self._app_id(), "strUser": self.username,
                "nTimeStamp": timestamp, "strRandom": rand,
                "strSign": signature, "strToken": token}

    async def _post(self, cmd, values, fields=""):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        data = ",".join("N'" + str(v).replace("'", "''") + "'" for v in values)
        try:
            async with self._session.post(
                self.server + "/APP/AppJson.asp", data=self._encode_command(
                    cmd, data, fields), timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                response.raise_for_status()
                body = await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RuntimeError(f"SinoTrack network error: {type(err).__name__}") from err
        try:
            result = json.loads(body)
        except (json.JSONDecodeError, TypeError) as err:
            raise RuntimeError("SinoTrack returned invalid JSON") from err
        if not isinstance(result, dict):
            raise RuntimeError("SinoTrack returned an unexpected response")
        return result

    @staticmethod
    def _first_value(response):
        if not isinstance(response, dict):
            return None
        fields = [str(v).lower() for v in (response.get("m_arrField") or [])]
        rows = response.get("m_arrRecord") or []
        if rows and isinstance(rows[0], list):
            if "result" in fields:
                try:
                    return str(rows[0][fields.index("result")])
                except (IndexError, ValueError):
                    pass
            return str(rows[0][0]) if rows[0] else None
        return None

    async def _ensure_login(self):
        if self._logged_in:
            return
        user, password = self.username[:23], self.password[:23]
        info = await self._post("Proc_GetLoginType", [user, password])
        try:
            login_type = int(self._first_value(info))
        except (TypeError, ValueError) as err:
            raise RuntimeError("Could not determine SinoTrack login type") from err
        command = {0: "Proc_Login", 1: "Proc_LoginAnother",
                   2: "Proc_LoginIMEI"}.get(login_type)
        if command is None:
            raise RuntimeError(f"Unsupported SinoTrack login type {login_type!r}")
        result = await self._post(command, [user, password])
        if not result.get("m_isResultOk") or self._first_value(result) != "1":
            raise RuntimeError("SinoTrack login was rejected")
        self._logged_in = True

    @staticmethod
    def _records(response):
        if not isinstance(response, dict):
            return []
        rows = response.get("m_arrRecord") or response.get("m_arrData") or []
        fields = response.get("m_arrField") or response.get("Field") or []
        if isinstance(fields, str):
            fields = fields.split(",")
        if isinstance(rows, dict):
            return [rows]
        if rows and isinstance(rows[0], list) and fields:
            return [dict(zip(fields, row)) for row in rows]
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _number(row, *keys):
        for key in keys:
            try:
                value = row.get(key)
                if value not in (None, ""):
                    number = float(value)
                    if number == number and abs(number) != float("inf"):
                        return number
            except (TypeError, ValueError):
                continue
        return None

    async def async_get_car_info(self, device_id, force_refresh=False):
        """Get initial mileage, cached for ten minutes."""
        now = time.monotonic()
        cached = self._initial_mileage_cache.get(str(device_id))
        if cached and not force_refresh and now - cached[1] < 600:
            return cached[0]
        await self._ensure_login()
        result = await self._post("Proc_GetCarInfo", [device_id])
        if not result.get("m_isResultOk"):
            raise RuntimeError("SinoTrack car-info request failed")
        for row in self._records(result):
            row_id = str(row.get("strTEID", row.get("strDeviceID", row.get("strIMEI", ""))))
            if row_id == str(device_id):
                initial = self._number(row, "nMileageInit")
                if initial is None:
                    raise RuntimeError("SinoTrack car info omitted initial mileage")
                self._initial_mileage_cache[str(device_id)] = (initial, now)
                return initial
        raise RuntimeError("SinoTrack car info returned no matching vehicle")

    async def async_get_position(self, device_id):
        await self._ensure_login()
        initial_km = await self.async_get_car_info(device_id)
        result = await self._post("Proc_GetLastPosition", [self.username])
        if not result.get("m_isResultOk", True):
            raise RuntimeError("SinoTrack position request failed")
        for row in self._records(result):
            row_id = str(row.get("strTEID", row.get("strDeviceID", row.get("strIMEI", ""))))
            if row_id == str(device_id):
                return self._normalise(row, initial_km)
        raise RuntimeError("SinoTrack returned no position for configured device")

    @staticmethod
    def parse_timestamp(value):
        """Parse epoch seconds/milliseconds or common date-time formats."""
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)) or (
            isinstance(value, str) and value.strip().replace(".", "", 1).isdigit()
        ):
            try:
                stamp = float(value)
                if stamp > 1e11:
                    stamp /= 1000
                if stamp <= 0:
                    return None
                return datetime.fromtimestamp(stamp, timezone.utc)
            except (ValueError, OverflowError, OSError):
                return None
        if isinstance(value, str):
            text = value.strip()
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
            except ValueError:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
                            "%Y/%m/%d %H:%M:%S"):
                    try:
                        return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
        return None

    @classmethod
    def gps_fix_age_seconds(cls, value):
        stamp = cls.parse_timestamp(value)
        if stamp is None:
            return None
        return max(0, int((datetime.now(timezone.utc) - stamp).total_seconds()))

    def _normalise(self, row, initial_km):
        raw = self._number(row, "nMileage")
        live_km = max(0.0, raw / 1000.0) if raw is not None else None
        total_km = max(0.0, initial_km + live_km) if live_km is not None else None
        timestamp = row.get("nTime", row.get("m_nTime", row.get("time")))
        parsed = self.parse_timestamp(timestamp)
        return {
            "latitude": self._number(row, "dbLat", "m_nLat", "latitude"),
            "longitude": self._number(row, "dbLon", "m_nLon", "longitude"),
            "speed": self._number(row, "nSpeed", "m_nSpeed", "speed"),
            "heading": self._number(row, "nDirection", "m_nDirection", "heading"),
            "timestamp": timestamp,
            "last_gps_update": parsed.isoformat() if parsed else None,
            "gps_fix_age_seconds": self.gps_fix_age_seconds(timestamp),
            "odometer_miles": total_km / KM_PER_MILE if total_km is not None else None,
            "odometer_km": total_km,
            "start_mileage": initial_km,
            "device_id": row.get("strTEID", row.get("strDeviceID", row.get("strIMEI"))),
        }
