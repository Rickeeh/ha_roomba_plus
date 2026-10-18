"""Removing entities for things the robot no longer has.

WHY THIS EXISTS
---------------

Home Assistant registers an entity the first time it appears and keeps
the row forever. `restored: true` is what that looks like from the
outside: "I knew this once."

Nothing in this integration ever removed one. @ScenicSystemsLLC found
five stale favourite entities on each of three robots -- deleted in the
iRobot app, still listed in Home Assistant, needing manual removal. He
placed it correctly as the same class as the repair issues that
survived his reinstall.

Three platforms create entities from a list the cloud provides:
favourites, consumable parts, and the maintenance to-dos built from the
same parts.

WHAT MAKES THIS SAFE
--------------------

**Only ever from a list that arrived.** A robot that is offline reports
nothing, and concluding from silence that its entities are obsolete
would delete them on every disconnection.

So each caller passes the ids it actually received, and an empty list
removes nothing at all -- an empty response is indistinguishable from
a failed one, and the cost of guessing wrong is a user's dashboard.

The prefix scoping matters too: `_favorite_` removes only favourites,
`_prime_part_` only parts. A robot with no favourites must not lose its
sensors because the favourites list came back empty.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import MAINTENANCE_DIAGNOSTIC_KEYS

_LOGGER = logging.getLogger(__name__)


@callback
def async_remove_stale_entities(
    hass: HomeAssistant,
    config_entry: Any,
    *,
    prefix: str,
    live_unique_ids: set[str],
) -> int:
    """Remove entities under `prefix` whose unique id is not live.

    `prefix` scopes the sweep to one kind of thing -- `_favorite_`,
    `_prime_part_`. `live_unique_ids` is what the cloud just reported.

    Returns the number removed, for the caller's log line.

    NOTHING IS REMOVED FOR AN EMPTY SET. A robot with no favourites and
    a favourites fetch that failed look identical from here, and the
    second must not delete the first's entities.
    """
    if not live_unique_ids:
        return 0

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(
        registry, config_entry.entry_id
    )

    removed = 0
    for entry in entries:
        unique_id = entry.unique_id or ""
        if prefix not in unique_id:
            continue
        if unique_id in live_unique_ids:
            continue
        _LOGGER.debug(
            "roomba_plus: removing %s -- %r is no longer reported",
            entry.entity_id, unique_id,
        )
        registry.async_remove(entry.entity_id)
        removed += 1

    if removed:
        _LOGGER.info(
            "roomba_plus: removed %d stale %s entit%s",
            removed, prefix.strip("_"), "y" if removed == 1 else "ies",
        )
    return removed


@callback
def async_remove_entities_by_suffix(
    hass: HomeAssistant,
    config_entry: Any,
    suffixes: dict[str, str],
    reason: str,
) -> int:
    """Remove this entry's entities whose unique id ends in a suffix
    given for their domain ({domain: suffix}).

    For entities an earlier version created on a capability the robot
    does not have. The CALLER decides that the robot lacks it, from data
    that arrived -- never from an empty or missing state, for the same
    reason as above.
    """
    registry = er.async_get(hass)
    removed = 0
    for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        suffix = suffixes.get(entry.domain)
        if suffix and (entry.unique_id or "").endswith(f"_{suffix}"):
            _LOGGER.info("roomba_plus: removing %s -- %s", entry.entity_id, reason)
            registry.async_remove(entry.entity_id)
            removed += 1
    return removed


@callback
def async_remove_prime_only_entities(hass: HomeAssistant, config_entry: Any) -> int:
    """Remove the entry's Prime-only entities, for an entry that moves
    from the cloud-only path to the local connection (4.5.0). Returns how
    many.

    The entities both paths create keep their unique id, so they stay
    the same entity with their name, area and history. The Prime-only
    ones would sit there as `restored: true` forever. They are the ones
    whose unique id carries `_prime_` right after the robot's prefix --
    the naming every Prime-only entity follows -- and the local path
    creates none of those, so nothing removed here comes back.

    The CALLER decides the robot is no longer on the Prime path, from a
    local connection that just worked (config_flow's reconfigure); this
    never runs on a guess.
    """
    blid = str((getattr(config_entry, "data", None) or {}).get("blid") or "")
    if not blid:
        return 0
    prefix = f"roomba_plus_{blid}_prime_"
    registry = er.async_get(hass)
    removed = 0
    for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        if (entry.unique_id or "").startswith(prefix):
            _LOGGER.info(
                "roomba_plus: removing %s -- the robot moved to the local connection",
                entry.entity_id,
            )
            registry.async_remove(entry.entity_id)
            removed += 1
    return removed


@callback
def async_set_maintenance_diagnostics_hidden(
    hass: HomeAssistant, config_entry: Any, hidden: bool,
) -> int:
    """Hide or show the maintenance diagnostic entities (4.5.0, E2).

    "Last replaced", "wear rate" and "days until due" per part: their
    figures are attributes of the part sensors now, and a new
    installation creates them disabled. This takes an existing one to the
    same set, on request -- and back. Hiding disables them as the
    integration; showing enables only what the integration disabled, never
    an entity the user switched off himself. Home Assistant reloads the
    entry to bring enabled entities back.

    Returns the number changed.
    """
    suffixes = tuple(f"_{key}" for key in MAINTENANCE_DIAGNOSTIC_KEYS)
    registry = er.async_get(hass)
    changed = 0
    for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        unique_id = entry.unique_id if isinstance(entry.unique_id, str) else ""
        if entry.domain != "sensor" or not unique_id.endswith(suffixes):
            continue
        if hidden and entry.disabled_by is None:
            registry.async_update_entity(
                entry.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION,
            )
            changed += 1
        elif not hidden and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
            registry.async_update_entity(entry.entity_id, disabled_by=None)
            changed += 1
    return changed
