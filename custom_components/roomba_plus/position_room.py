"""Which room the robot is in, from where it is (4.4.0).

THE ROOM FROM THE POSITION, WHERE THERE IS ONE (@frnchfrgg). Room
tracking moves through the planned rooms on phase changes and drives,
and decides whether a room is done from how long the robot has been in
it against an estimate. A robot that cleans in another order, or a run
whose rooms took longer or shorter than estimated, gives room changes
that never happened.

A robot that reports its position, or answers when asked for it, says
where it is. Where that position can be placed in a room -- a Smart Map
whose rooms the aligner has placed, or a 900-series whose floor Roomba+
has divided into areas -- the room comes from there instead:

  * A room counts once the robot has stayed in it for DWELL_SEC, with
    at least MIN_SAMPLES positions. A robot crossing a doorway, or
    passing through a hall, does not change the room.
  * A position outside every room (a doorway, floor the map does not
    cover) changes nothing.
  * Positions that stop for STALE_SEC hand room tracking back to the
    phase changes and estimates (callbacks.py).

This module only decides. callbacks._apply_position_room() moves the
room display and fires the room events.
"""

from __future__ import annotations

from collections.abc import Callable
import math
from time import monotonic
from typing import Any

#: Seconds in a room before it counts.
DWELL_SEC = 15.0
#: Positions in a room before it counts (with DWELL_SEC).
MIN_SAMPLES = 3
#: Seconds without a position after which room tracking falls back.
STALE_SEC = 60.0
#: How recent a position must be to say the robot is still in a room
#: it was told to skip (4.4.1).
SKIP_STILL_IN_SEC = 10.0

#: Grid cell of the 900-series areas (room_seg_store.CELL_MM).
_SEG_CELL_MM = 150.0


class PositionRoomTracker:
    """Turns a stream of rooms-at-a-position into confirmed room changes."""

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._listeners: list[Callable[[str | None, str], None]] = []
        self.reset()

    def reset(self) -> None:
        """Forget the room; a new mission starts from no room."""
        #: The confirmed room, or None.
        self.current: str | None = None
        self._candidate: str | None = None
        self._candidate_since = 0.0
        self._candidate_samples = 0
        #: When the last position arrived (clock), and its room.
        self.last_seen: float | None = None
        self.last_room: str | None = None
        #: When a position last lay in a room (clock). Only these make
        #: the tracker active: positions no room can be found for must
        #: not switch off the phase-based room tracking.
        self.last_in_room: float | None = None
        #: Confirmed changes this mission (diagnostics).
        self.changes = 0
        #: Positions this mission per room, None for those in no room
        #: (4.4.1, diagnostics): a turn that puts the path beside the
        #: floor plan shows as positions in no room, without a
        #: coordinate leaving the house.
        self.counts: dict[str | None, int] = {}

    def add_listener(
        self, listener: Callable[[str | None, str], None]
    ) -> Callable[[], None]:
        """Call `listener(previous, room)` on every confirmed change."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    def observe(self, room: str | None) -> None:
        """One position, in `room` or in none."""
        now = self._clock()
        self.last_seen = now
        self.last_room = room
        self.counts[room] = self.counts.get(room, 0) + 1
        if room is None:
            return
        self.last_in_room = now
        if room == self.current:
            self._candidate = None
            return
        if room != self._candidate:
            self._candidate = room
            self._candidate_since = now
            self._candidate_samples = 1
            return
        self._candidate_samples += 1
        if (
            now - self._candidate_since >= DWELL_SEC
            and self._candidate_samples >= MIN_SAMPLES
        ):
            previous, self.current = self.current, room
            self._candidate = None
            self.changes += 1
            for listener in list(self._listeners):
                listener(previous, room)

    def active(self) -> bool:
        """Whether positions are arriving: room tracking follows them."""
        return (
            self.last_in_room is not None
            and self._clock() - self.last_in_room <= STALE_SEC
        )

    def diagnostics(self) -> dict[str, Any]:
        """Room names and counts only; no position."""
        return {
            "active": self.active(),
            "current": self.current,
            "candidate": self._candidate,
            "last_position_room": self.last_room,
            "seconds_since_position": (
                round(self._clock() - self.last_seen, 1)
                if self.last_seen is not None
                else None
            ),
            "changes_this_mission": self.changes,
            # Room names and counts; "(none)" for positions in no room.
            "positions_by_room": {
                ("(none)" if room is None else room): n
                for room, n in sorted(
                    self.counts.items(), key=lambda kv: (kv[0] is None, kv[0] or "")
                )
            },
        }

    def still_in(self, room: str) -> bool:
        """Whether the latest position, a moment ago, lay in `room`."""
        return (
            self.last_room == room
            and self.last_seen is not None
            and self._clock() - self.last_seen <= SKIP_STILL_IN_SEC
        )


def room_at_position(data: Any, x_mm: float, y_mm: float, *, frame: str) -> str | None:
    """The room a position lies in, or None where none can be said.

    `frame` "umf": a position requested from a Smart Map robot, turned
    into the cloud map's own frame (image._handle_live_position) -- the
    frame the aligner keeps the rooms in. "pose": the robot's own
    position, converted by the aligner on a Smart Map robot, or looked
    up in the areas Roomba+ divided a 900-series floor into.
    """
    if not (math.isfinite(x_mm) and math.isfinite(y_mm)):
        return None
    aligner = getattr(data, "umf_aligner", None)
    if frame == "umf":
        # Already in the rooms' frame: no alignment needed, only rooms.
        if aligner is None:
            return None
        name = aligner.room_name_at(x_mm, y_mm)
        return str(name) if name else None
    if aligner is not None and getattr(aligner, "aligned", False):
        point = aligner.pose_to_umf(x_mm, y_mm)
        if point is None:
            return None
        name = aligner.room_name_at(*point)
        return str(name) if name else None
    return _seg_room_at(getattr(data, "room_seg_store", None), x_mm, y_mm)


def _seg_room_at(store: Any, x_mm: float, y_mm: float) -> str | None:
    """The 900-series area at a position: its cell, or one next to it.

    The areas are cells the robot covered, so a position on an area's
    edge can fall just outside; one cell around is searched, nearest
    first. Hidden areas are not rooms anyone named or wants.
    """
    rooms = getattr(store, "rooms", None)
    if not isinstance(rooms, dict) or not rooms:
        return None
    gx = int(math.floor(x_mm / _SEG_CELL_MM))
    gy = int(math.floor(y_mm / _SEG_CELL_MM))
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        cell = (gx + dx, gy + dy)
        for room in rooms.values():
            if getattr(room, "hidden", False):
                continue
            if cell in getattr(room, "cells", ()):
                return _seg_room_name(room)
    return None


def _seg_room_name(room: Any) -> str:
    """An area's name, or "Area N" as the naming form shows it."""
    name = getattr(room, "name", "")
    if name:
        return str(name)
    room_id = str(getattr(room, "id", ""))
    return f"Area {room_id.removeprefix('room_')}"
