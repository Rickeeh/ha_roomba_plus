"""iRobot's parts catalogue and the guide link per part (I4)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.roomba_plus import parts_catalog as pc

CATALOGUE = {
    "buyPartsUrl": "https://store.example/parts",
    "parts": [
        {"part_id": 67, "part_name": "Filter",
         "guide_url": "https://help.irobot.com/filter", "buy_url": "https://x"},
        {"part_id": "71", "part_name": "Brushes", "guide_url": ""},
        {"partId": 147, "partName": "Dirt bag", "guideUrl": "https://help.irobot.com/bag"},
        {"part_name": "No id"},
        {"part_id": 9, "guide_url": "http://insecure.example/guide"},
    ],
}


class TestParse:
    def test_links_join_by_part_id_and_only_real_ones_count(self):
        parsed = pc.parse_catalogue(CATALOGUE)
        assert parsed["67"] == {"guide_url": "https://help.irobot.com/filter",
                                "buy_url": "https://x", "part_name": "Filter"}
        assert parsed["71"] == {"part_name": "Brushes"}, "an empty guide is no guide"
        assert parsed["147"]["guide_url"] == "https://help.irobot.com/bag"
        assert "guide_url" not in parsed.get("9", {}), "https only"

    @pytest.mark.parametrize("payload", [None, [], {"parts": None}, "x"])
    def test_anything_else_is_empty(self, payload):
        assert pc.parse_catalogue(payload) == {}


class TestLocale:
    @pytest.mark.parametrize(
        ("language", "country", "expected"),
        [
            ("de", "DE", ("de-DE", "DE")),
            ("de", "AT", ("de-AT", "AT")),
            ("en-GB", None, ("en-GB", "GB")),
            ("pt-BR", "BR", ("pt-BR", "BR")),
            ("fr", None, ("en-US", "US")),
        ],
    )
    def test_the_path_wants_language_with_region_and_a_country(self, language, country, expected):
        hass = SimpleNamespace(config=SimpleNamespace(language=language, country=country))
        assert pc.catalogue_locale(hass) == expected


class TestFetch:
    def _session(self, status=200, payload=CATALOGUE, raises=None):
        resp = MagicMock(status=status)
        resp.json = AsyncMock(return_value=payload)
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        if raises:
            session.get.side_effect = raises
        else:
            session.get.return_value = ctx
        return session

    @pytest.mark.asyncio
    async def test_the_url_carries_locale_and_sku(self):
        hass = SimpleNamespace(config=SimpleNamespace(language="de", country="DE"))
        session = self._session()
        with patch.object(pc, "async_get_clientsession", return_value=session):
            parsed = await pc.async_fetch_catalogue(hass, "i755840")
        assert session.get.call_args.args[0] == (
            "https://content-prod.iot.irobotapi.com/v2/de-DE/DE/i755840/parts"
        )
        assert parsed["67"]["guide_url"].endswith("/filter")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kwargs", [{"status": 404}, {"raises": OSError("down")}])
    async def test_a_failed_read_costs_the_links_only(self, kwargs):
        hass = SimpleNamespace(config=SimpleNamespace(language="en", country="US"))
        with patch.object(pc, "async_get_clientsession", return_value=self._session(**kwargs)):
            assert await pc.async_fetch_catalogue(hass, "i755840") == {}

    @pytest.mark.asyncio
    async def test_no_sku_no_request(self):
        session = self._session()
        with patch.object(pc, "async_get_clientsession", return_value=session):
            assert await pc.async_fetch_catalogue(MagicMock(), None) == {}
        session.get.assert_not_called()


class TestTheSensorsShowTheGuide:
    def test_a_prime_part(self):
        from custom_components.roomba_plus.sensor_prime import PrimeConsumablePartSensor

        entry = MagicMock()
        part = SimpleNamespace(part_id="67", count_type="minutes", count_used=10,
                               minutes_remaining=100, count_remaining=100,
                               counter_category="replacement")
        entry.runtime_data.prime_parts_coordinator.data = {"67": part}
        entry.runtime_data.parts_catalogue = pc.parse_catalogue(CATALOGUE)
        sensor = PrimeConsumablePartSensor("B", "67", entry)
        assert sensor.extra_state_attributes["guide_url"] == "https://help.irobot.com/filter"

        entry.runtime_data.parts_catalogue = {}
        assert "guide_url" not in sensor.extra_state_attributes

    def test_a_classic_consumable_through_its_cloud_part(self):
        from custom_components.roomba_plus.sensor_core import SENSORS, RoombaSensor

        description = next(d for d in SENSORS if d.consumable_role == "filter")
        sensor = RoombaSensor.__new__(RoombaSensor)
        sensor.entity_description = description
        entry = MagicMock()
        entry.options = {}
        store = MagicMock()
        store.cloud_part_by_role.return_value = {"part_id": 67}
        store.cloud_full_life_hours.return_value = 150
        entry.runtime_data.maintenance_store = store
        entry.runtime_data.parts_catalogue = pc.parse_catalogue(CATALOGUE)
        sensor._config_entry = entry
        sensor.vacuum_state = {}

        attrs = sensor.extra_state_attributes
        assert attrs["guide_url"] == "https://help.irobot.com/filter"
        store.cloud_part_by_role.assert_called_with("filter")


class TestTheEntriesHearOfIt:
    """4.5.0: the catalogue arrives after the maintenance entries were
    built; its links reach them through a recompute."""

    @pytest.mark.asyncio
    async def test_a_loaded_catalogue_is_announced(self):
        data = SimpleNamespace(blid="B1", parts_catalogue={})
        sent = []
        with patch.object(pc, "async_fetch_catalogue", AsyncMock(return_value={"35": {"part_name": "Filter"}})), \
                patch.object(pc, "async_fetch_help", AsyncMock(return_value={})), \
                patch.object(pc, "async_dispatcher_send", lambda hass, signal: sent.append(signal)):
            await pc.async_load_into(MagicMock(), data, "R980020")
        assert data.parts_catalogue == {"35": {"part_name": "Filter"}}
        assert sent == ["roomba_plus_maintenance_changed_B1"]

    @pytest.mark.asyncio
    async def test_an_empty_one_is_not(self):
        data = SimpleNamespace(blid="B1", parts_catalogue={})
        sent = []
        with patch.object(pc, "async_fetch_catalogue", AsyncMock(return_value={})), \
                patch.object(pc, "async_fetch_help", AsyncMock(return_value={})), \
                patch.object(pc, "async_dispatcher_send", lambda hass, signal: sent.append(signal)):
            await pc.async_load_into(MagicMock(), data, "R980020")
        assert sent == []


#: The shape of the help catalogue's answer (read 19.10.2026 for R980020
#: and G185020), trimmed: placeholder URLs, two of the real id spellings.
HELP = {
    "customerCarePhone": "+00 0000000",
    "otherContent": [
        {"id": "Error 2", "content": "https://help.example/8957.html"},
        {"id": "Charging Error 4", "content": "https://help.example/19560.html"},
        {"id": "Charging Error19", "content": "https://help.example/19562.html"},
        {"id": "Charging error 21", "content": "https://help.example/26166.html"},
        {"id": "Charging Error 104", "content": "https://help.example/10604.html"},
        {"id": "Start-Refuse 22", "content": "https://help.example/222.html"},
        {"id": "Error 9", "content": "http://insecure.example/9"},
        {"id": None, "content": "https://help.example/none"},
        "not an entry",
    ],
}


class TestTheHelpCatalogue:
    """4.5.0: iRobot's article for an error, per robot model and language."""

    def test_ids_are_compared_without_case_and_spaces(self):
        """The Classic catalogue spells 119 and 121 two ways each."""
        parsed = pc.parse_help(HELP)
        assert parsed["chargingerror19"].endswith("/19562.html")
        assert parsed["chargingerror21"].endswith("/26166.html")
        assert "error9" not in parsed, "https only"

    @pytest.mark.parametrize("payload", [None, [], {"otherContent": None}, "x"])
    def test_anything_else_is_empty(self, payload):
        assert pc.parse_help(payload) == {}

    def test_classic_and_prime_number_charging_errors_differently(self):
        data = SimpleNamespace(help_catalogue=pc.parse_help(HELP))
        assert pc.help_url_for(data, 104, prime=False).endswith("/19560.html")
        assert pc.help_url_for(data, 104, prime=True).endswith("/10604.html")
        assert pc.help_url_for(data, 121, prime=False).endswith("/26166.html")
        assert pc.help_url_for(data, 222, prime=True).endswith("/222.html")
        assert pc.help_url_for(data, 2, prime=False).endswith("/8957.html")

    def test_no_link_without_an_entry(self):
        data = SimpleNamespace(help_catalogue=pc.parse_help(HELP))
        assert pc.help_url_for(data, 48, prime=False) is None
        assert pc.help_url_for(data, 0, prime=False) is None
        assert pc.help_url_for(SimpleNamespace(), 2, prime=False) is None
        assert pc.help_url_for(None, 2, prime=False) is None

    @pytest.mark.asyncio
    async def test_the_url_carries_the_bare_language_and_the_month(self):
        hass = SimpleNamespace(config=SimpleNamespace(language="de", country="DE"))
        session = TestFetch()._session(payload=HELP)
        with patch.object(pc, "async_get_clientsession", return_value=session):
            parsed = await pc.async_fetch_help(hass, "R980020")
        assert session.get.call_args.args[0] == (
            "https://content-prod.iot.irobotapi.com/v2/help/de/DE/R980020"
        )
        assert session.get.call_args.kwargs["params"]["track"].count(".") == 1
        assert parsed["error2"].endswith("/8957.html")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kwargs", [{"status": 404}, {"raises": OSError("down")}])
    async def test_a_failed_read_costs_the_links_only(self, kwargs):
        hass = SimpleNamespace(config=SimpleNamespace(language="en", country="US"))
        with patch.object(pc, "async_get_clientsession", return_value=TestFetch()._session(**kwargs)):
            assert await pc.async_fetch_help(hass, "R980020") == {}

    @pytest.mark.asyncio
    async def test_no_sku_no_request(self):
        session = TestFetch()._session()
        with patch.object(pc, "async_get_clientsession", return_value=session):
            assert await pc.async_fetch_help(MagicMock(), None) == {}
        session.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_it_is_read_with_the_parts_catalogue(self):
        data = SimpleNamespace(blid="B1", parts_catalogue={}, help_catalogue={})
        with patch.object(pc, "async_fetch_catalogue", AsyncMock(return_value={})), \
                patch.object(pc, "async_fetch_help", AsyncMock(return_value={"error2": "https://h/2"})):
            await pc.async_load_into(MagicMock(), data, "R980020")
        assert data.help_catalogue == {"error2": "https://h/2"}
