"""Pro.SinoTrack API client."""
import base64
import hashlib
import time
import random
import json
import logging
import aiohttp
_LOGGER = logging.getLogger(__name__)
ROW = "\x11"
TABLE = "\x1b"
KM_PER_MILE = 1.609344
class SinoTrackApi:
    def __init__(self, server, username, password, session=None):
        self.server = server.rstrip("/")
        self.username = username
        self.password = password
        self._session = session
        self._owns_session = session is None
        self._logged_in = False
    async def async_close(self):
        if self._owns_session and self._session:
            await self._session.close()
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
            pad_seed = "MGTS_" + str(int(random.random() * 10**14)).zfill(14)
            token_raw += pad_seed[7]
        token = self._b64(token_raw)
        timestamp = str(int(time.time() * 1000))
        rand = seed.replace("MGTS_", "")
        signature = hashlib.md5(
            (
                timestamp
                + rand
                + self.username
                + self._app_id()
                + token
            ).encode("utf-8")
        ).hexdigest()
        return {
            "strAppID": self._app_id(),
            "strUser": self.username,
            "nTimeStamp": timestamp,
            "strRandom": rand,
            "strSign": signature,
            "strToken": token,
        }
    async def _post(self, cmd, values, fields=""):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        data = ",".join(
            "N'" + str(value).replace("'", "''") + "'"
            for value in values
        )
        payload = self._encode_command(cmd, data, fields)
        url = self.server + "/APP/AppJson.asp"
        async with self._session.post(
            url,
            data=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            response.raise_for_status()
            body = await response.text()
        try:
            return json.loads(body)
        except Exception as err:
            raise RuntimeError(
                f"SinoTrack returned non-JSON response: {body[:160]}"
            ) from err
    @staticmethod
    def _first_value(response):
        if not isinstance(response, dict):
            return None
        fields = [
            str(value).lower()
            for value in (response.get("m_arrField") or [])
        ]
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
        user = self.username[:23]
        password = self.password[:23]
        login_type_response = await self._post(
            "Proc_GetLoginType",
            [user, password],
        )
        try:
            login_type = int(self._first_value(login_type_response))
        except (TypeError, ValueError):
            raise RuntimeError(
                "SinoTrack could not determine the login type"
            )
        commands = {
            0: "Proc_Login",
            1: "Proc_LoginAnother",
            2: "Proc_LoginIMEI",
        }
        command = commands.get(login_type)
        if command is None:
            raise RuntimeError(
                f"SinoTrack returned unsupported login type {login_type!r}"
            )
        login = await self._post(command, [user, password])
        result_value = self._first_value(login)
        if (
            not isinstance(login, dict)
            or not login.get("m_isResultOk")
            or result_value != "1"
        ):
            raise RuntimeError(
                f"SinoTrack login rejected after {command}"
            )
        self._logged_in = True
    @staticmethod
    def _records(response):
        """Convert SinoTrack field/record arrays into dictionaries."""
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
                    return float(value)
            except (TypeError, ValueError):
                continue
        return None
    async def async_get_car_info(self, device_id):
        """Get the configured initial mileage in kilometres."""
        await self._ensure_login()
        result = await self._post(
            "Proc_GetCarInfo",
            [device_id],
        )
        if not isinstance(result, dict) or not result.get("m_isResultOk"):
            raise RuntimeError("SinoTrack car-info request failed")
        for row in self._records(result):
            row_id = str(
                row.get(
                    "strTEID",
                    row.get("strDeviceID", row.get("strIMEI", "")),
                )
            )
            if row_id == str(device_id):
                initial_km = self._number(row, "nMileageInit")
                if initial_km is None:
                    raise RuntimeError(
                        "SinoTrack car info did not contain nMileageInit"
                    )
                return initial_km
        raise RuntimeError(
            f"SinoTrack car info returned no vehicle {device_id}"
        )
    async def async_get_position(self, device_id):
        await self._ensure_login()
        # Configured initial mileage, in kilometres.
        initial_km = await self.async_get_car_info(device_id)
        result = await self._post(
            "Proc_GetLastPosition",
            [self.username],
        )
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected position response")
        for row in self._records(result):
            row_id = str(
                row.get(
                    "strTEID",
                    row.get("strDeviceID", row.get("strIMEI", "")),
                )
            )
            if row_id == str(device_id):
                return self._normalise(row, initial_km)
        raise RuntimeError(
            f"SinoTrack returned no position row for device {device_id}. "
            f"Response keys: {list(result.keys())}"
        )
    def _normalise(self, row, initial_km):
        def num(*keys):
            return self._number(row, *keys)
        # The saved SinoTrack website divides raw nMileage by 1000
        # to convert metres into kilometres.
        raw_live_mileage = num("nMileage")
        live_km = (
            max(0.0, raw_live_mileage / 1000.0)
            if raw_live_mileage is not None
            else 0.0
        )
        total_km = max(0.0, initial_km + live_km)
        total_miles = total_km / KM_PER_MILE
        return {
            "latitude": num("dbLat", "m_nLat", "latitude"),
            "longitude": num("dbLon", "m_nLon", "longitude"),
            "speed": num("nSpeed", "m_nSpeed", "speed"),
            "heading": num("nDirection", "m_nDirection", "heading"),
            "timestamp": row.get(
                "nTime",
                row.get("m_nTime", row.get("time")),
            ),
            "odometer_miles": total_miles,
            "odometer_km": total_km,
            "start_mileage": initial_km,
            "device_id": row.get(
                "strTEID",
                row.get("strDeviceID", row.get("strIMEI")),
            ),
            "raw": row,
        }