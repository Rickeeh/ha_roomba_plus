"""Which Prime parts are due, and what they are -- without the platforms.

Split out of the Prime to-do list (4.2.19) so that the household API can
ask the same question: the list imported the entity base, which imports
the package root, which imports `api_views`, and the API could not
import the rule from there without a cycle. The maintenance model reads
it too (4.5.0), and the list itself is built from the model since the
Prime list module went. Plain functions over the runtime data, no Home
Assistant imports.
"""
from __future__ import annotations

import re
from typing import Any


#: Part id -> the dock capability flag that has to be present for it to
#: mean anything. From `capabilityFromKey`, app 3.0.0.
_PART_REQUIRES_DOCK_CAP: dict[str, str] = {
    "147": "evac",   # dust bag -- needs an evacuating dock
    "202": "pw",     # pad wash cleaning
    "212": "pw",     # pad wash replacement
}


def parts_the_robot_cannot_have(config_entry: Any) -> set[str]:
    """Parts whose dock capability the robot reports as absent.

    Explicit denial only. `dock.cap.evac == 0` means "this dock does not
    evacuate"; a missing block means the robot said nothing, and
    silence is not a denial.
    """
    data = getattr(config_entry, "runtime_data", None)
    coordinator = getattr(data, "prime_status_coordinator", None)
    shadows = getattr(coordinator, "data", None)
    if not isinstance(shadows, dict):
        return set()
    caps: dict[str, Any] = {}
    for body in shadows.values():
        dock = body.get("dock") if isinstance(body, dict) else None
        if isinstance(dock, dict) and isinstance(dock.get("cap"), dict):
            caps.update(dock["cap"])
    if not caps:
        return set()
    return {
        part_id
        for part_id, flag in _PART_REQUIRES_DOCK_CAP.items()
        if caps.get(flag) == 0
    }


def needs_attention(part: Any) -> bool:
    """Whether the robot says this part is due.

    ZERO MEANS TWO OPPOSITE THINGS, depending on the category.

    On a `replacement` part it means used up. On a `maintenance` part it
    means **just done** -- the counter resets when the job is performed,
    so a freshly washed pad reads zero and needs nothing.

    @DaRealGuGu's robot made that plain. Two parts count the same 90 pad
    washes:

        212  replacement  count_remaining 210   the pad itself
        202  maintenance  count_remaining 0     the wash

    The pad has 210 washes of life left; the wash has zero *since the
    last one*. Reading both the same way put an item on his list while
    the iRobot app showed nothing due and the robot's own light ring was
    clear.

    The category was already being read -- for the verb, "Clean" versus
    "Replace". It decides this too, and did not.

    **HOW FAR THIS IS ESTABLISHED:** one account, one robot, and the app
    agreeing. Whether a `maintenance` counter ever climbs to signal a job
    that IS due is unknown, so nothing here treats it as due. Being quiet
    about a real job is recoverable; nagging about a clean pad is how a
    list gets ignored, and the items that mattered go with it.
    """
    category = str(getattr(part, "counter_category", "") or "").lower()
    if category == "maintenance":
        return False
    remaining = getattr(part, "count_remaining", None)
    return isinstance(remaining, (int, float)) and remaining <= 0


def prime_parts_due(config_entry: Any) -> list[str]:
    """Ids of the parts a Prime robot reports as due, sorted.

    THE MAINTENANCE LIST'S OWN RULE, so every place that asks "is
    maintenance due" on Prime gets the list's answer: `needs_attention`
    for what counts as due, minus the parts the robot's dock says it does
    not have. The household API read Classic's local hour counters for
    this, which a Prime robot never reports -- so a Prime robot was never
    due there, whatever its parts said.
    """
    coordinator = getattr(
        getattr(config_entry, "runtime_data", None), "prime_parts_coordinator", None
    )
    parts = getattr(coordinator, "data", None)
    if not isinstance(parts, dict):
        return []
    absent = parts_the_robot_cannot_have(config_entry)
    return sorted(
        str(part_id)
        for part_id, part in parts.items()
        if str(part_id) not in absent and needs_attention(part)
    )


# ── Which part it is (4.5.0) ─────────────────────────────────────────────────

#: The Prime app's own rule for what a part is (app 3.2.0): the first of
#: these words found in the part's name decides, in this order -- so a
#: "mop washing system" is not taken for a mop pad. The app knows no
#: numeric part ids at all; it reads the name.
PRIME_ROLE_KEYWORDS: tuple[str, ...] = (
    "mop_washing_system",
    "dock_washing_system",
    "main_brush",
    "side_brush",
    "detergent",
    "filter",
    "pad",
    "bag",
    "roller",
    "sensor",
)

#: Numeric ids matched against the app by value (see sensor_prime's
#: _KNOWN_PARTS for who confirmed which). They come first: a match
#: against the app's own screen is better evidence than a name. 202 and
#: 212 are not here -- nobody found them in the app -- so their name,
#: where the catalogue has one, decides.
_PRIME_NUMERIC_ROLES: dict[str, str] = {
    "67": "side_brush",
    "69": "main_brush",
    "71": "main_brush",
    "68": "filter",
    "72": "filter",
    "147": "bag",
    "148": "pad",
    "149": "pad",
    "213": "sensor",
}


def _name_key(text: Any) -> str:
    """"Main Brush" and "main-brush" as "main_brush"."""
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")


def prime_part_role(part_id: Any, part_name: Any = None) -> str | None:
    """The role of a Prime part, or None when nothing names it.

    The id where it was matched against the app; otherwise the app's
    keyword rule over the id itself (servers since app 3.0.0 send
    speaking ids such as `main_brush`) and then over the catalogue's
    part name.
    """
    pid = str(part_id or "").strip()
    if pid in _PRIME_NUMERIC_ROLES:
        return _PRIME_NUMERIC_ROLES[pid]
    for text in (pid, part_name):
        key = _name_key(text)
        if not key:
            continue
        for keyword in PRIME_ROLE_KEYWORDS:
            if keyword in key:
                return keyword
    return None


def part_count_in_display_unit(part: Any, count: int | None) -> int | None:
    """A part count expressed in the unit its sensor shows.

    THE TABLE RENAMES A UNIT AND THE VALUE HAS TO FOLLOW. `minutes` is
    displayed as hours, so a count in minutes has to be divided before
    it is shown beside that word. Every other count type is displayed in
    the unit the robot already counts in and passes through untouched.

    Shared because it was not. The sensor divided; the maintenance list
    looked up the same table for the same part and printed the raw
    number beside the renamed unit, so one robot showed `179 h` on
    `sensor.*_prime_part_69` and "10740 hours remaining" on its
    maintenance list at the same moment -- the same value, one of them
    sixty times too large (@utkjmitch, part 69, confirmed against the
    iRobot app's "Multi-surface brush 179 hrs").

    A number and the word it is labelled with cannot drift apart if
    both come from here. Moved here from sensor_prime (4.5.0) so the
    maintenance model can use it without importing an entity module.
    """
    if count is None:
        return None
    if (getattr(part, "count_type", "") or "").lower() == "minutes":
        # Minutes on the wire, hours in the app -- 5100 -> 85 h,
        # confirmed on two accounts and then by count_type itself.
        return round(count / 60)
    return count
