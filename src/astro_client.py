"""
astro_client.py
---------------
HTTP wrapper around freeastrologyapi.com.
All methods return the raw parsed JSON dict from the API.
"""

import json
import requests

BASE_URL = "https://json.freeastrologyapi.com"
WARNINGS_FILTER = True  # suppress urllib3 SSL warning noise


class AstroClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{BASE_URL}{path}"
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("statusCode") not in (200, None):
            raise RuntimeError(f"API error on {path}: {data}")
        return data

    @staticmethod
    def _base_payload(birth: dict) -> dict:
        """Strip extra keys; return the 9 required birth fields."""
        return {
            "year":      birth["year"],
            "month":     birth["month"],
            "date":      birth["date"],
            "hours":     birth["hours"],
            "minutes":   birth["minutes"],
            "seconds":   birth.get("seconds", 0),
            "latitude":  birth["latitude"],
            "longitude": birth["longitude"],
            "timezone":  birth["timezone"],
        }

    # ------------------------------------------------------------------
    # Vedic (Jyotish) endpoints — Lahiri ayanamsha
    # ------------------------------------------------------------------

    def get_vedic_planets(self, birth: dict) -> dict:
        """
        POST /planets
        Returns planet positions + house numbers in the sidereal (Lahiri) system.
        Response key: output  →  dict with numeric string keys "0"–"12"
        Each entry: {name, fullDegree, normDegree, isRetro, current_sign, house_number}
        Ascendant (index 0) has no house_number.
        """
        payload = {
            **self._base_payload(birth),
            "settings": {
                "observation_point": "topocentric",
                "ayanamsha": "lahiri",
            },
        }
        return self._post("/planets", payload)

    def get_shad_bala(self, birth: dict) -> dict:
        """
        POST /shadbala/summary
        Returns the six-fold planetary strength for Sun–Saturn.
        Response key: output → dict keyed by planet name
        Each entry: {Shadbala, rupas, percentage_strength, ishta_phala, kashta_phala}
        """
        payload = {
            **self._base_payload(birth),
            "config": {
                "observation_point": "topocentric",
                "ayanamsha": "lahiri",
            },
        }
        return self._post("/shadbala/summary", payload)

    def get_maha_dasas(self, birth: dict) -> dict:
        """
        POST /vimsottari/maha-dasas
        Returns the complete 120-year Vimsottari Dasa sequence.
        NOTE: response["output"] is a JSON *string* — must be json.loads'd.
        Each entry: {Lord, start_time, end_time}
        """
        payload = {
            **self._base_payload(birth),
            "config": {
                "observation_point": "topocentric",
                "ayanamsha": "lahiri",
            },
        }
        raw = self._post("/vimsottari/maha-dasas", payload)
        # The API returns output as a stringified JSON object — parse it here
        if isinstance(raw.get("output"), str):
            raw["output"] = json.loads(raw["output"])
        return raw

    # ------------------------------------------------------------------
    # Western astrology endpoints — tropical ayanamsha
    # ------------------------------------------------------------------

    def get_western_planets(self, birth: dict) -> dict:
        """
        POST /western/planets
        Returns tropical planet positions including outer planets, Chiron, asteroids.
        Response key: output → list of planet objects
        Each: {planet: {en}, fullDegree, normDegree, isRetro, zodiac_sign: {number, name}}
        """
        payload = {
            **self._base_payload(birth),
            "config": {
                "observation_point": "topocentric",
                "ayanamsha": "tropical",
            },
        }
        return self._post("/western/planets", payload)

    def get_western_houses(self, birth: dict) -> dict:
        """
        POST /western/houses
        Returns Placidus house cusps in tropical system.
        Response key: output.Houses → list of 12 house objects
        Each: {House (1-12), degree, normDegree, zodiac_sign: {number, name}}
        """
        payload = {
            **self._base_payload(birth),
            "config": {
                "observation_point": "topocentric",
                "ayanamsha": "tropical",
                "house_system": "Placidus",
            },
        }
        return self._post("/western/houses", payload)

    def get_western_aspects(self, birth: dict) -> dict:
        """
        POST /western/aspects
        Returns all planetary aspects detected within standard orbs.
        Response key: output → list of aspect objects
        Each: {planet_1: {en}, planet_2: {en}, aspect: {en}}
        """
        payload = {
            **self._base_payload(birth),
            "config": {
                "observation_point": "topocentric",
                "ayanamsha": "tropical",
            },
        }
        return self._post("/western/aspects", payload)

    # ------------------------------------------------------------------
    # Convenience: fetch everything in one call
    # ------------------------------------------------------------------

    def get_full_chart_data(self, birth: dict) -> dict:
        """
        Fetch all six data sets needed for the Self Map and return them in a
        single dict with descriptive keys.

        Keys returned:
            vedic_planets, shad_bala, maha_dasas,
            western_planets, western_houses, western_aspects
        """
        import time

        def _fetch(fn):
            """Retry once on 429 with a 2-second back-off."""
            try:
                return fn(birth)
            except Exception as e:
                if "429" in str(e):
                    time.sleep(2)
                    return fn(birth)
                raise

        results = {}
        for key, fn in [
            ("vedic_planets",   self.get_vedic_planets),
            ("shad_bala",       self.get_shad_bala),
            ("maha_dasas",      self.get_maha_dasas),
            ("western_planets", self.get_western_planets),
            ("western_houses",  self.get_western_houses),
            ("western_aspects", self.get_western_aspects),
        ]:
            results[key] = _fetch(fn)
            time.sleep(0.4)   # stay well within rate limits

        return results
