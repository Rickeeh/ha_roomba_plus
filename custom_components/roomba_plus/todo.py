"""The maintenance list, `todo.<robot>_maintenance`, on both generations.

ONE ITEM PER MAINTENANCE ENTRY (maintenance_model.py, 4.5.0): every part
the robot has, every care task with care reminders on, and a "check"
item while the robot reports an error that points to a care task. The
list computes nothing itself; it shows the entries every other surface
shows, and ticking an item off is `roomba_plus.maintenance_done` --
on Prime the reset goes to iRobot, as the app sends it.

OPEN FROM "DUE", NOT FROM "SOON" (E4). An item that is not due is listed
as done, with its due date; "soon" shows on the status sensor and the
part sensors. So the list's count is what needs doing now, and is zero
while nothing does -- ten items permanently open is a badge nobody
looks at. A snoozed item stays done until its snooze ends.

THE LIST USED TO CALL A REPLACEMENT A CLEANING. Its brush item read
"Clean brush roll" and ticking it reset the main-brush replacement
counter -- so cleaning the brushes weekly, as the item invited, kept the
replacement reminder from ever coming due. Replacing and cleaning are
separate entries, with separate effects.

PRIME WAS READ-ONLY until 4.5.0: the reset had never been sent. It is
sent now, with the body the app sends (roombapy-prime's
reset_robot_parts), and a reset iRobot does not apply is an error the
user sees, not a tick that silently comes undone.

THE DESCRIPTION IS MARKDOWN. Home Assistant's list renders it -- bold
and links, in the browser and the companion app (L6, checked) -- and
the edit dialog shows it raw. So it carries the remaining count, the
error that brought the item, and links: our care guide (care_guides.py),
iRobot's guide and the part.

WORDING COMES FROM THE TRANSLATIONS (selector `maintenance_item`):
Home Assistant does not translate to-do summaries. English below is the
fallback if the table cannot be read.

NAME THE ROOMS -- a live status item on a Classic robot, not an
action. It clears itself once every room on the map has a name.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .care_guides import (
    ENGLISH_WORDING,
    RobotContext,
    context_for,
    guide_link,
    guide_why,
)
from .const import DOMAIN
from .entity import IRobotEntity
from .maintenance_model import (
    ACTION_CHECK,
    ACTION_CLEAN,
    ACTION_REPLACE,
    LEVEL_DUE,
    LEVEL_OVERDUE,
    MaintenanceItem,
)
from .maintenance_store import _parse
from .models import ConnectionType, RoombaConfigEntry
from .room_cleaning import smart_rooms_to_name
from .sensor_prime import _KNOWN_PARTS
from .zone_naming import unlabelled_zone_ids

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

#: English wording, used when the translation table cannot be read.
#: Keys match `selector.maintenance_item.options` in strings.json; it
#: lives beside the care guides, which read it too.
_ENGLISH = ENGLISH_WORDING

#: The wording key of an entry, where it differs from "{action}_{part}".
_SUMMARY_KEYS: dict[tuple[str, str], str] = {
    (ACTION_REPLACE, "main_brush"): "replace_main_brushes",
    (ACTION_REPLACE, "pad"): "replace_mop_pad",
    (ACTION_REPLACE, "bag"): "replace_dust_bag",
    (ACTION_CLEAN, "sensor"): "clean_cliff_sensors",
}

#: Item uids the list used before 4.5.0, kept so an automation keyed on
#: one keeps working. Everything else uses the entry's id.
_LEGACY_UIDS: dict[str, str] = {
    "replace.filter": "filter_maintenance",
    "replace.main_brush": "brush_maintenance",
    "replace.side_brush": "side_brush_maintenance",
    "replace.clean_base_bag": "clean_base_bag_maintenance",
    "replace.pad": "pad_maintenance",
}


def _uid(item: MaintenanceItem, prime: bool) -> str:
    """The list's uid for an entry: the one it had before 4.5.0 where
    there was one -- `care_<task>` for a care task, `part_<id>` for a
    Prime part -- and the entry's id otherwise."""
    if prime and item.part_id is not None and item.action != ACTION_CHECK:
        return f"part_{item.part_id}"
    if item.action == ACTION_CLEAN and item.part_id is None:
        return f"care_{item.part}"
    return _LEGACY_UIDS.get(item.id, item.id)


def _readable_part_name(hass: Any, part_id: str) -> str:
    """A Prime part's display name, or its id if we have none.

    Reads the same translation the part sensors use, so the list and the
    sensors agree, without the "Maintenance – " grouping the sensor names
    carry. Falls back to the bare id rather than to a key -- "Replace:
    68" is a question somebody can ask; "Replace prime_part_edge_brush"
    looks like a bug because it is one (@utkjmitch, a30 and a31).
    """
    key = _KNOWN_PARTS.get(part_id)
    if not isinstance(key, str):
        return part_id
    try:
        from homeassistant.helpers.translation import (  # noqa: PLC0415
            async_get_cached_translations,
        )

        cached = async_get_cached_translations(hass, hass.config.language, "entity")
        name = cached.get(f"component.{DOMAIN}.entity.sensor.{key}.name")
    except Exception:  # noqa: BLE001
        name = None
    if isinstance(name, str) and name:
        return name.split(" – ", 1)[-1]
    return key.replace("prime_part_", "").replace("_", " ").title()


class MaintenanceWording:
    """The entries' wording in Home Assistant's language, for the list
    and the maintenance calendar alike: summary, Markdown description.
    Needs `self.hass`; `_async_load_wording()` once when added."""

    hass: Any
    _wording: dict[str, str]

    async def _async_load_wording(self) -> None:
        """The item texts in Home Assistant's language, once."""
        try:
            from homeassistant.helpers.translation import (  # noqa: PLC0415
                async_get_translations,
            )

            table = await async_get_translations(
                self.hass, self.hass.config.language, "selector", {DOMAIN}
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Maintenance list: no translation table", exc_info=True)
            return
        prefix = f"component.{DOMAIN}.selector.maintenance_item.options."
        self._wording = {
            key[len(prefix):]: text
            for key, text in table.items()
            if key.startswith(prefix) and isinstance(text, str)
        }

    def _text(self, key: str) -> str:
        wording = getattr(self, "_wording", None) or {}
        return wording.get(key) or _ENGLISH[key]

    def _summary(self, item: MaintenanceItem) -> str:
        key = _SUMMARY_KEYS.get((item.action, item.part), f"{item.action}_{item.part}")
        if key in _ENGLISH:
            return self._text(key)
        # The part's name in Home Assistant's language: ours for a role,
        # the part sensor's for a numbered part, the number otherwise.
        if item.part_id is not None and item.part.startswith("part_"):
            name = _readable_part_name(self.hass, item.part_id)
        elif f"part_{item.part}" in _ENGLISH:
            name = self._text(f"part_{item.part}")
        else:
            name = item.part.replace("_", " ")
        generic = "clean_part" if item.action == ACTION_CLEAN else "replace_part"
        return self._text(generic).replace("{part}", name)

    def _description(
        self, item: MaintenanceItem, entry_id: str, ctx: RobotContext | None = None,
    ) -> str | None:
        lines: list[str] = []
        # What the part does, in one sentence (concept B): the guide's own.
        why = guide_why(self.hass, item.guide_id, ctx)
        if why:
            lines.append(why)
        if item.error is not None:
            lines.append(self._text("error_line").replace("{code}", str(item.error)))
        elif item.reason is not None and f"reason_{item.reason}" in _ENGLISH:
            lines.append(self._text(f"reason_{item.reason}"))
        if item.action == ACTION_CLEAN and item.interval_unit == "days" and item.interval:
            lines.append(self._text("every_days").replace("{days}", f"{item.interval:g}"))
        elif item.remaining is not None and item.unit and f"unit_{item.unit}" in _ENGLISH:
            lines.append(
                self._text("left")
                .replace("{value}", f"{item.remaining:g}")
                .replace("{unit}", self._text(f"unit_{item.unit}"))
            )
        ours = guide_link(self.hass, entry_id, item.guide_id)
        links = [
            f"[{self._text(key)}]({url})"
            for key, url in (
                ("link_care_guide", ours),
                ("link_guide", item.guide_url),
                ("link_buy", item.buy_url),
            )
            if url
        ]
        if links:
            lines.append(" · ".join(links))
        return "\n\n".join(lines) or None



class RoombaMaintenanceTodo(MaintenanceWording, IRobotEntity, TodoListEntity):
    """The maintenance entries as a to-do list, both generations."""

    _attr_translation_key = "maintenance"
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM
    _shows_maintenance = True

    def __init__(self, roomba: Any, blid: str, config_entry: RoombaConfigEntry) -> None:
        super().__init__(roomba, blid, config_entry)
        self._config_entry = config_entry
        self._attr_unique_id = f"{self.robot_unique_id}_maintenance"

    @property
    def suggested_object_id(self) -> str:
        return "maintenance"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_load_wording()

    @property
    def _prime(self) -> bool:
        return (
            getattr(self._config_entry.runtime_data, "connection_type", None)
            is ConnectionType.CLOUD_ONLY
        )

    # ── Items ────────────────────────────────────────────────────────────────

    def _entries(self) -> list[MaintenanceItem]:
        tracker = getattr(self._config_entry.runtime_data, "maintenance", None)
        if tracker is None:
            return []
        # The battery of a Classic robot has no interval and is never
        # due; it is an entry so a new pack can be recorded, not a task.
        return [i for i in tracker.items if not (i.part == "battery" and i.used is None)]

    @property
    def todo_items(self) -> list[TodoItem]:
        """Built from the entries on every call: nothing here is cached."""
        now = dt_util.now()
        prime = self._prime
        ctx = context_for(self._config_entry.runtime_data)
        items: list[TodoItem] = []
        for entry in self._entries():
            snoozed = _parse(entry.snoozed_until)
            open_now = entry.level in (LEVEL_DUE, LEVEL_OVERDUE) and not (
                snoozed is not None and snoozed > now
            )
            due = _parse(entry.due)
            items.append(TodoItem(
                summary=self._summary(entry),
                uid=_uid(entry, prime),
                status=TodoItemStatus.NEEDS_ACTION if open_now else TodoItemStatus.COMPLETED,
                due=dt_util.as_local(due).date() if due is not None else None,
                description=self._description(entry, self._config_entry.entry_id, ctx),
            ))
        if not prime and self._rooms_need_naming():
            items.append(TodoItem(
                summary=self._text("reconfigure_rooms"),
                uid="reconfigure_rooms",
                status=TodoItemStatus.NEEDS_ACTION,
                description=self._text("reconfigure_rooms_description"),
            ))
        return items

    def _rooms_need_naming(self) -> bool:
        """The same question the "Rooms & zones" step answers.

        WITH AN IROBOT ACCOUNT, rooms take their names from it, and only
        a room on the map without a name anywhere needs one. Checked
        against the robot's own region ids, this item stood open for
        a tester's i7 while every room on his map had its name.
        """
        options = self._config_entry.options
        data = getattr(self._config_entry, "runtime_data", None)
        coordinator = getattr(data, "cloud_coordinator", None)
        if coordinator is not None and getattr(coordinator, "data", None) is not None:
            return bool(smart_rooms_to_name(data, options))
        return bool(unlabelled_zone_ids(self.vacuum_state, options))

    # ── Ticking off ──────────────────────────────────────────────────────────

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Ticking an item off is `maintenance_done` for its entry.

        Only the step to COMPLETED does anything: there is no "undo a
        replacement", and an item unticked shows its real state again.
        A Prime reset iRobot does not apply raises, and the list says so.
        """
        if item.status != TodoItemStatus.COMPLETED:
            return
        tracker = getattr(self._config_entry.runtime_data, "maintenance", None)
        prime = self._prime
        entry = next(
            (e for e in self._entries() if _uid(e, prime) == item.uid), None
        )
        # "reconfigure_rooms": deliberately no action -- it clears itself.
        if tracker is not None and entry is not None:
            await tracker.async_done(entry.id, via="todo")
        self.async_write_ha_state()

    # ── Push update wiring ────────────────────────────────────────────────────

    def new_state_filter(self, new_state: dict[str, Any]) -> bool:
        """The entries arrive through the maintenance recompute; the
        robot's own messages matter for the rooms item only."""
        return "cleanSchedule2" in new_state or "lastCommand" in new_state


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoombaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """The maintenance list, for a robot with maintenance entries."""
    data = config_entry.runtime_data
    if getattr(data, "maintenance", None) is None:
        return
    roomba = None if data.connection_type is ConnectionType.CLOUD_ONLY else data.roomba
    async_add_entities([RoombaMaintenanceTodo(roomba, data.blid, config_entry)])
