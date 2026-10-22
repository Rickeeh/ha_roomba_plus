"""Tests for todo.py: the maintenance list on both generations.

4.5.0 builds the list from the maintenance entries (maintenance_model.py):
one item per part and care task, a "check" item while an error points to
a care task, open from "due", ticking = maintenance_done. The Prime list
module went with it; its tests that still apply live here.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.todo import TodoItem, TodoItemStatus

from custom_components.roomba_plus.maintenance_model import MaintenanceItem
from custom_components.roomba_plus.models import ConnectionType

_ZONES = "custom_components.roomba_plus.todo.unlabelled_zone_ids"
_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _make_todo(items=(), *, prime=False, tracker="stub", vacuum_state=None, **options):
    from custom_components.roomba_plus.todo import RoombaMaintenanceTodo

    todo = RoombaMaintenanceTodo.__new__(RoombaMaintenanceTodo)
    todo._blid = "TESTBLID"
    todo.vacuum_state = vacuum_state if vacuum_state is not None else {"sku": "R980020"}
    todo.hass = MagicMock()
    todo.hass.config.language = "en"
    todo._config_entry = MagicMock()
    todo._config_entry.entry_id = "test_entry"
    todo._config_entry.options = options
    data = todo._config_entry.runtime_data
    data.cloud_coordinator = None
    data.connection_type = ConnectionType.CLOUD_ONLY if prime else ConnectionType.LOCAL_PUSH
    if tracker == "stub":
        tracker = SimpleNamespace(items=list(items), async_done=AsyncMock())
    data.maintenance = tracker
    todo._wording = {}
    todo.async_write_ha_state = MagicMock()
    return todo


def _items(todo, zones=()):
    with patch(_ZONES, return_value=list(zones)):
        return {i.uid: i for i in todo.todo_items}


def _item(item_id, action, part, **kw):
    return MaintenanceItem(item_id, action, part, **kw)


class TestAsyncSetupEntry:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", [ConnectionType.LOCAL_PUSH, ConnectionType.CLOUD_ONLY])
    async def test_one_list_for_either_generation(self, kind):
        from custom_components.roomba_plus.todo import RoombaMaintenanceTodo, async_setup_entry

        config_entry = MagicMock()
        config_entry.runtime_data.connection_type = kind
        config_entry.runtime_data.blid = "TESTBLID"
        added: list = []
        await async_setup_entry(MagicMock(), config_entry, added.extend)
        assert len(added) == 1 and isinstance(added[0], RoombaMaintenanceTodo)
        assert added[0].unique_id == "roomba_plus_TESTBLID_maintenance"
        assert added[0].suggested_object_id == "maintenance"
        from homeassistant.components.todo import TodoListEntityFeature

        assert added[0].supported_features & TodoListEntityFeature.UPDATE_TODO_ITEM

    @pytest.mark.asyncio
    async def test_none_without_maintenance_entries(self):
        from custom_components.roomba_plus.todo import async_setup_entry

        config_entry = MagicMock()
        config_entry.runtime_data.maintenance = None
        added: list = []
        await async_setup_entry(MagicMock(), config_entry, added.extend)
        assert added == []


class TestOpenFromDue:
    """E4: open from "due"; "soon" shows elsewhere. Zero open while
    nothing is due."""

    def test_only_due_and_overdue_are_open(self):
        items = _items(_make_todo([
            _item("replace.filter", "replace", "filter", level="soon"),
            _item("replace.main_brush", "replace", "main_brush", level="due"),
            _item("replace.side_brush", "replace", "side_brush", level="overdue"),
            _item("replace.clean_base_bag", "replace", "clean_base_bag"),
        ]))
        assert items["filter_maintenance"].status == TodoItemStatus.COMPLETED
        assert items["brush_maintenance"].status == TodoItemStatus.NEEDS_ACTION
        assert items["side_brush_maintenance"].status == TodoItemStatus.NEEDS_ACTION
        assert items["clean_base_bag_maintenance"].status == TodoItemStatus.COMPLETED

    def test_a_snoozed_item_stays_done_until_its_snooze_ends(self):
        later = (datetime.now(UTC) + timedelta(days=2)).isoformat()
        earlier = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        items = _items(_make_todo([
            _item("replace.filter", "replace", "filter", level="due", snoozed_until=later),
            _item("replace.main_brush", "replace", "main_brush", level="due", snoozed_until=earlier),
        ]))
        assert items["filter_maintenance"].status == TodoItemStatus.COMPLETED
        assert items["brush_maintenance"].status == TodoItemStatus.NEEDS_ACTION

    def test_the_classic_battery_is_not_a_task(self):
        assert _items(_make_todo([_item("replace.battery", "replace", "battery")])) == {}

    def test_no_entries_no_items(self):
        assert _items(_make_todo(tracker=None)) == {}


class TestUidsAndWording:

    def test_uids_kept_from_before(self):
        items = _items(_make_todo([
            _item("replace.pad", "replace", "pad"),
            _item("clean.wheel", "clean", "wheel", interval=14, interval_unit="days"),
            _item("check.bin", "check", "bin", level="due", error=14),
        ]))
        assert set(items) == {"pad_maintenance", "care_wheel", "check.bin"}
        assert items["pad_maintenance"].summary == "Replace the mop pad"
        assert items["care_wheel"].summary == "Clean the wheels"
        assert items["check.bin"].summary == "Check the bin"

    def test_prime_parts_keep_their_part_uid_and_read_as_words(self):
        items = _items(_make_todo([
            _item("replace.bag", "replace", "bag", part_id="147"),
            _item("clean.mop_washing_system", "clean", "mop_washing_system", part_id="202"),
            _item("clean.sensor", "clean", "sensor", part_id="213"),
            _item("replace.part_999", "replace", "part_999", part_id="999"),
            _item("clean.part_888", "clean", "part_888", part_id="888"),
            _item("replace.roller", "replace", "roller", part_id="r"),
            _item("clean.pad", "clean", "pad", part_id="p"),
        ], prime=True))
        assert items["part_147"].summary == "Replace the dust bag"
        assert items["part_202"].summary == "Clean the mop washing system"
        assert items["part_213"].summary == "Clean the cliff sensors"
        assert items["part_999"].summary == "Replace: 999"
        assert items["part_888"].summary == "Clean: 888"
        assert items["part_r"].summary == "Replace the roller mop"
        assert items["part_p"].summary == "Clean: mop pad"

    def test_a_part_without_wording_of_its_own_is_named_in_the_users_language(self):
        """A role with no item text of its own -- "clean the main brush"
        on a Prime robot -- reads in Home Assistant's language, not in
        the role's English key."""
        todo = _make_todo(
            [_item("clean.main_brush", "clean", "main_brush", part_id="m"),
             _item("replace.mystery", "replace", "mystery", part_id="x")],
            prime=True,
        )
        todo._wording = {"clean_part": "Reinigen: {part}", "part_main_brush": "Hauptbürsten"}
        items = _items(todo)
        assert items["part_m"].summary == "Reinigen: Hauptbürsten"
        assert items["part_x"].summary == "Replace: mystery"

    def test_no_summary_contains_a_translation_key(self):
        """@utkjmitch, a30 and a31: "Replace prime_part_dirt_bag"."""
        items = _items(_make_todo(
            [_item("replace.part_68x", "replace", "part_147", part_id="147")], prime=True,
        ))
        assert not any("prime_part" in i.summary for i in items.values())

    def test_the_description_is_markdown_with_what_is_left_the_error_and_links(self):
        items = _items(_make_todo([
            _item("replace.filter", "replace", "filter", level="due", remaining=8.0,
                  unit="hours", guide_url="https://g", buy_url="https://b", error=26),
            _item("clean.filter", "clean", "filter", interval=3.5, interval_unit="days",
                  remaining=1.5, unit="days"),
            _item("replace.part_1", "replace", "part_1", remaining=3.0, unit="weird"),
        ]))
        assert items["filter_maintenance"].description == (
            "The robot reports error 26.\n\n8 hours left\n\n"
            "[iRobot's guide](https://g) · [Buy the part](https://b)"
        )
        assert items["care_filter"].description == "Every 3.5 days, as iRobot recommends."
        assert items["replace.part_1"].description is None

    def test_irobots_article_for_the_error_is_linked(self):
        """4.5.0b4: beside iRobot's guide for the part, its article for
        the error that brought the entry."""
        items = _items(_make_todo([
            _item("check.bin", "check", "bin", level="due", error=14,
                  help_url="https://example.com/error-14"),
        ]))
        assert items["check.bin"].description.endswith(
            "[iRobot's article on the error](https://example.com/error-14)"
        )

    def test_the_part_says_what_it_does_and_why_the_robot_stopped(self):
        """Concept B: one sentence of what the part does, from the guide
        in the robot's variant; a reason that is not an error says so."""
        from custom_components.roomba_plus.care_guides import _DATA_KEY, CareGuides, _read_files

        texts, schemata = _read_files()
        todo = _make_todo([
            _item("check.bin", "check", "bin", level="due", reason="bin_full",
                  guide_id="clean_bin"),
        ])
        todo.hass.data = {_DATA_KEY: CareGuides(b"k" * 32, texts, schemata)}
        lines = _items(todo)["check.bin"].description.split("\n\n")
        assert lines[0] == texts["en"]["clean_bin"]["why"]
        assert lines[1] == "The bin is full."
        assert lines[2].startswith('<a href="/api/roomba_plus/care/test_entry/clean_bin?')

    def test_our_care_guide_comes_first_signed_and_relative(self):
        from custom_components.roomba_plus.care_guides import _DATA_KEY, CareGuides

        todo = _make_todo([
            _item("replace.filter", "replace", "filter", guide_url="https://g",
                  guide_id="replace_filter"),
        ])
        todo.hass.data = {_DATA_KEY: CareGuides(b"k" * 32, {}, {})}
        text = _items(todo)["filter_maintenance"].description
        # HTML with a target: a Markdown link to Home Assistant's own host
        # was taken over by the frontend's router and opened the overview.
        assert text.startswith(
            '<a href="/api/roomba_plus/care/test_entry/replace_filter?lang=en&amp;exp='
        ), "no texts loaded: no sentence before it"
        assert '&amp;sig=' in text and '" target="_blank">How to do it</a>' in text
        assert text.endswith(" · [iRobot's guide](https://g)"), "another host: Markdown"

    def test_the_calendar_keeps_the_markdown_link(self):
        """The calendar shows a description as plain text; HTML there
        would only be noise."""
        from custom_components.roomba_plus.calendar import RoombaMaintenanceCalendar
        from custom_components.roomba_plus.todo import RoombaMaintenanceTodo

        assert RoombaMaintenanceTodo._LINKS_AS_HTML is True
        assert RoombaMaintenanceCalendar._LINKS_AS_HTML is False

    def test_a_due_date(self):
        items = _items(_make_todo([
            _item("replace.filter", "replace", "filter", due="2026-10-20T12:00:00+00:00"),
        ]))
        assert items["filter_maintenance"].due.isoformat() == "2026-10-20"


class TestReadablePartNames:

    def _name(self, part_id, cached=None, error=None):
        from custom_components.roomba_plus.todo import _readable_part_name

        hass = MagicMock()
        hass.config.language = "en"
        kwargs = {"side_effect": error} if error else {"return_value": cached or {}}
        with patch("homeassistant.helpers.translation.async_get_cached_translations", **kwargs):
            return _readable_part_name(hass, part_id)

    def test_a_translated_name_without_the_grouping(self):
        assert self._name("72", {
            "component.roomba_plus.entity.sensor.prime_part_filter.name":
                "Maintenance – High-Efficiency Filter",
        }) == "High-Efficiency Filter"

    def test_an_untranslated_key_still_reads_as_words(self):
        assert self._name("147") == "Dirt Bag"

    def test_an_unknown_id_falls_back_to_its_number(self):
        assert self._name("999") == "999"

    def test_a_broken_translation_lookup_does_not_break_the_list(self):
        assert self._name("147", error=RuntimeError("boom")) == "Dirt Bag"


class TestWording:
    @pytest.mark.asyncio
    async def test_loaded_from_the_selector_table(self):
        todo = _make_todo()
        todo.hass.config.language = "de"
        table = {
            "component.roomba_plus.selector.maintenance_item.options.clean_filter": "Filter reinigen",
            "component.roomba_plus.selector.other.options.x": "nope",
        }
        with patch("homeassistant.helpers.translation.async_get_translations",
                   AsyncMock(return_value=table)):
            await todo._async_load_wording()
        assert todo._wording == {"clean_filter": "Filter reinigen"}

    @pytest.mark.asyncio
    async def test_a_failed_read_keeps_english(self):
        todo = _make_todo()
        with patch("homeassistant.helpers.translation.async_get_translations",
                   AsyncMock(side_effect=RuntimeError)):
            await todo._async_load_wording()
        assert todo._text("clean_filter") == "Clean the filter"

    def test_every_key_has_a_translation_and_an_english_fallback(self):
        import json
        from pathlib import Path

        from custom_components.roomba_plus.todo import _ENGLISH

        strings = json.loads(Path("custom_components/roomba_plus/strings.json").read_text())
        assert strings["selector"]["maintenance_item"]["options"] == _ENGLISH

    @pytest.mark.asyncio
    async def test_added_to_hass_loads_wording(self):
        from custom_components.roomba_plus import todo as todo_mod

        todo = _make_todo()
        with patch.object(todo_mod.IRobotEntity, "async_added_to_hass", AsyncMock()), \
             patch.object(type(todo), "_async_load_wording", AsyncMock()) as load:
            await todo.async_added_to_hass()
        load.assert_awaited_once()
        assert todo._shows_maintenance is True


class TestReconfigureRooms:
    def test_present_when_unlabelled_zones_exist(self):
        item = _items(_make_todo(), zones=["7"])["reconfigure_rooms"]
        assert item.due is None
        assert "Rooms & zones" in item.description
        assert item.summary == "Name the rooms"

    def test_absent_when_no_unlabelled_zones(self):
        assert "reconfigure_rooms" not in _items(_make_todo())

    def test_never_on_prime(self):
        assert "reconfigure_rooms" not in _items(_make_todo(prime=True), zones=["7"])

    def _with_account(self, todo, unnamed):
        coordinator = MagicMock()
        coordinator.data = {"pmaps": []}
        todo._config_entry.runtime_data.cloud_coordinator = coordinator
        return patch(
            "custom_components.roomba_plus.todo.smart_rooms_to_name",
            return_value=unnamed,
        )

    def test_with_an_account_the_rooms_on_the_map_decide(self):
        todo = _make_todo()
        with self._with_account(todo, []):
            assert "reconfigure_rooms" not in _items(todo, zones=["20", "21"])

    def test_with_an_account_an_unnamed_room_on_the_map_opens_it(self):
        todo = _make_todo()
        with self._with_account(todo, ["7"]):
            assert "reconfigure_rooms" in _items(todo)


class TestTickingOff:

    @pytest.mark.asyncio
    async def test_ticking_is_maintenance_done(self):
        todo = _make_todo([_item("replace.filter", "replace", "filter", level="due")])
        await todo.async_update_todo_item(TodoItem(
            uid="filter_maintenance", summary="x", status=TodoItemStatus.COMPLETED,
        ))
        todo._config_entry.runtime_data.maintenance.async_done.assert_awaited_once_with(
            "replace.filter", via="todo",
        )
        todo.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_a_prime_part_too(self):
        todo = _make_todo([_item("replace.bag", "replace", "bag", part_id="147")], prime=True)
        await todo.async_update_todo_item(TodoItem(
            uid="part_147", summary="x", status=TodoItemStatus.COMPLETED,
        ))
        todo._config_entry.runtime_data.maintenance.async_done.assert_awaited_once_with(
            "replace.bag", via="todo",
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("uid,status", [
        ("reconfigure_rooms", TodoItemStatus.COMPLETED),
        ("nothing", TodoItemStatus.COMPLETED),
        ("filter_maintenance", TodoItemStatus.NEEDS_ACTION),
    ])
    async def test_what_does_nothing(self, uid, status):
        todo = _make_todo([_item("replace.filter", "replace", "filter", level="due")])
        await todo.async_update_todo_item(TodoItem(uid=uid, summary="x", status=status))
        todo._config_entry.runtime_data.maintenance.async_done.assert_not_awaited()

    def test_robot_messages_matter_for_the_rooms_item_only(self):
        todo = _make_todo()
        assert todo.new_state_filter({"lastCommand": {}}) is True
        assert todo.new_state_filter({"cleanSchedule2": []}) is True
        assert todo.new_state_filter({"bbrun": {}}) is False


class TestWithTheRealEntries:
    """Through the real tracker: what the list shows is what the
    maintenance model says, and ticking moves it."""

    async def test_a_classic_robot(self, hass):
        from tests.test_maintenance_store import _tracker

        from custom_components.roomba_plus.maintenance_store import MaintenanceStore

        store = MaintenanceStore()
        store.profile_hours = {"filter": 50}
        tracker = _tracker(hass, store=store)
        await tracker.async_refresh()
        todo = _make_todo(tracker=tracker)
        items = _items(todo)
        assert items["filter_maintenance"].status == TodoItemStatus.NEEDS_ACTION
        assert items["brush_maintenance"].status == TodoItemStatus.COMPLETED
        with patch(
            "custom_components.roomba_plus.maintenance_model._async_push_part_reset_to_cloud",
            AsyncMock(),
        ):
            await todo.async_update_todo_item(TodoItem(
                uid="filter_maintenance", summary="x", status=TodoItemStatus.COMPLETED,
            ))
        assert _items(todo)["filter_maintenance"].status == TodoItemStatus.COMPLETED


class TestTheListIsOnForNewRobots:
    """E1 (4.5.0): on for a robot added from now on, off by default for
    one set up before -- it keeps its setting."""

    def _platforms(self, options):
        from custom_components.roomba_plus import _optional_platforms

        entry = MagicMock()
        entry.options = options
        return _optional_platforms(entry)

    def test_an_existing_robot_keeps_it_off(self):
        from homeassistant.const import Platform

        assert Platform.TODO not in self._platforms({})

    def test_present_when_switched_on(self):
        from homeassistant.const import Platform

        assert Platform.TODO in self._platforms({"enable_maintenance_list": True})

    def test_new_entries_start_with_it_on_in_options_and_data(self):
        import inspect

        from custom_components.roomba_plus import config_flow

        assert config_flow._NEW_INSTALL_OPTIONS == {"enable_maintenance_list": True}
        source = inspect.getsource(config_flow)
        assert source.count("options=dict(_NEW_INSTALL_OPTIONS)") == 2

    def test_one_option_governs_both_generations(self):
        import inspect

        from custom_components.roomba_plus import _optional_platforms

        assert inspect.getsource(_optional_platforms).count("CONF_ENABLE_MAINTENANCE_LIST") == 1

class TestASwitchedOffListLeavesNoEntityBehind:
    """@ScenicSystemsLLC (4.3.0b4): left-over `todo.*_maintenance`
    entities, "unavailable" and "restored", after the list went opt-in."""

    def _run(self, options):
        from custom_components.roomba_plus import _remove_switched_off_optional_entities

        config_entry = MagicMock()
        config_entry.options = options
        config_entry.entry_id = "entry1"
        entries = [
            MagicMock(domain="todo", entity_id="todo.robby_maintenance"),
            MagicMock(domain="calendar", entity_id="calendar.robby_schedule"),
            MagicMock(domain="sensor", entity_id="sensor.robby_battery"),
        ]
        fake_er = MagicMock()
        with patch("homeassistant.helpers.entity_registry.async_get", return_value=fake_er), patch(
            "homeassistant.helpers.entity_registry.async_entries_for_config_entry",
            return_value=entries,
        ):
            _remove_switched_off_optional_entities(MagicMock(), config_entry)
        return [c.args[0] for c in fake_er.async_remove.call_args_list]

    def test_the_list_off_removes_its_entity_and_nothing_else(self):
        assert self._run({}) == ["todo.robby_maintenance"]

    def test_the_list_on_keeps_it(self):
        assert self._run({"enable_maintenance_list": True}) == []
