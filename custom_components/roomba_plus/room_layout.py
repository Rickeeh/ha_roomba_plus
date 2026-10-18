"""room_layout.py -- straight walls, doors and furniture for 900-series areas (4.5.0).

WHY. The areas RoomSegStore keeps are the cells the robot drove over. Drawn
as they are, a room is a ragged blob: its edge stops wherever the robot
stopped, every bed is a hole and every corner is rounded. Checked against
the maintainer's flat, room by room, the walls behind those blobs are
simple: every wall between two rooms and every outer wall is straight, and
they run along the two axes the robot cleans in.

HOW, in five steps:

  1. THE AXES. A 900-series cleans in lanes along the walls. If a large
     share of its travel runs along the dock's own two axes, the walls do
     too (AXIS_TOLERANCE_DEG, MIN_AXIS_SHARE). The maintainer's 980: 42%
     of its travel within 2 degrees. Without that, no layout is drawn: a
     home with slanted walls gets the areas as before.
  2. ONE RECTANGLE PER ROOM, at the outermost floor the robot drove
     (TRIM leaves out single stray cells). Areas that share a name are one
     room. Floor inside a room that nothing drove is furniture -- the
     maintainer's beds, which the areas drew as holes.
  3. ONE WALL BETWEEN TWO ROOMS. Coverage stops a few centimetres short of
     a wall on both sides, so two rooms' facing sides lie a wall's
     thickness plus that margin apart. Sides that close meet halfway.
  4. WHO GETS AN OVERLAP. Rectangles of rooms that are not rectangles
     (a hall around a staircase) overlap their neighbours'. The most
     rectangular rooms are placed first; no room takes floor another room
     drove; what is left of a rectangle is the room.
  5. DOORS ARE GAPS, where the robot crossed between two rooms
     (RoomSegStore.note_paths): across the direction it crossed in, as
     wide as the configured door, or as wide as it measured when that is
     clearly wider (an open passage).

Pure and Home Assistant-free: areas and doors come in as plain values.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import math
import statistics

#: Grid cell (RoomSegStore.CELL_MM, GridStore.CELL_SIZE_MM).
CELL_MM = 150.0

#: Travel within this many degrees of the dock's axes counts as along them.
AXIS_TOLERANCE_DEG = 2.0
#: Share of travel along the axes from which walls are taken as straight
#: and axis-parallel. The maintainer's 980: 0.42. Uniform headings would
#: give 4 x 4 degrees / 90 = 0.18.
MIN_AXIS_SHARE = 0.25
#: Travel needed before the share means anything (mm).
MIN_TRAVEL_MM = 20_000.0
#: Steps that count for the heading: shorter ones are jitter, longer ones
#: gaps in the recording.
MIN_STEP_MM, MAX_STEP_MM = 40.0, 450.0

#: Share of a room's cells left out at each end of each axis: a stray
#: cell must not push a wall out.
TRIM = 0.003
#: How far short of a wall coverage stops, on each side (mm).
CLEAN_MARGIN_MM = 150.0
#: A measured opening this much wider than the configured door is an open
#: passage, drawn at its measured width.
OPEN_EXTRA_MM = 300.0
#: How far a door may lie from the wall it belongs in (cells).
DOOR_SNAP_CELLS = 2
#: Two rooms' rectangles overlapping in a strip at most this deep (cells)
#: share a ragged boundary, not floor: one straight line is drawn through
#: the strip, where it puts the fewest driven cells on the wrong side.
MAX_SEAM_CELLS = 4

DEFAULT_WALL_MM = 150.0
DEFAULT_DOOR_MM = 800.0
DEFAULT_ROBOT_DIAMETER_MM = 340.0

Cell = tuple[int, int]


@dataclass(frozen=True)
class AreaInput:
    """One room as the layout sees it: its key (the name, or the area id
    while it has none) and the cells the robot drove in it."""

    key: str
    cells: frozenset[Cell]


@dataclass(frozen=True)
class DoorInput:
    """A door between two rooms (keys as AreaInput.key), where it was
    found, and the crossings of it: (x_mm, y_mm, dx, dy) each."""

    room_a: str
    room_b: str
    cx: float
    cy: float
    crossings: tuple[tuple[float, float, float, float], ...] = ()


@dataclass(frozen=True)
class LayoutWall:
    """A straight wall from (x1, y1) to (x2, y2), mm."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class LayoutDoor:
    """A door: centre, whether its line runs along x, width, and whether
    it is an open passage rather than a door."""

    cx: float
    cy: float
    along_x: bool
    width_mm: float
    open: bool
    room_a: str
    room_b: str


@dataclass(frozen=True)
class RoomLayout:
    rooms: dict[str, frozenset[Cell]]
    walls: tuple[LayoutWall, ...]
    doors: tuple[LayoutDoor, ...]
    furniture: frozenset[Cell]
    axis_share: float
    wall_mm: float = DEFAULT_WALL_MM
    door_mm: float = DEFAULT_DOOR_MM
    unplaced_doors: int = 0

    def diagnostics(self) -> dict[str, object]:
        """Counts and sizes only, no position."""
        return {
            "axis_share": round(self.axis_share, 2),
            "rooms": len(self.rooms),
            "walls": len(self.walls),
            "wall_length_m": round(
                sum(math.hypot(w.x2 - w.x1, w.y2 - w.y1) for w in self.walls) / 1000, 1
            ),
            "doors": sum(1 for d in self.doors if not d.open),
            "open_passages": sum(1 for d in self.doors if d.open),
            "doors_not_placed": self.unplaced_doors,
            "furniture_m2": round(len(self.furniture) * (CELL_MM / 1000) ** 2, 1),
            "wall_thickness_mm": self.wall_mm,
            "door_width_mm": self.door_mm,
        }


# ── 1. The axes ────────────────────────────────────────────────────────────


def axis_share(paths: Iterable[Sequence[Sequence[float]]]) -> float | None:
    """Share of travel along the dock's two axes; None with too little."""
    along = total = 0.0
    for path in paths:
        prev: Sequence[float] | None = None
        for p in path:
            if prev is not None:
                dx, dy = p[0] - prev[0], p[1] - prev[1]
                step = math.hypot(dx, dy)
                if MIN_STEP_MM < step < MAX_STEP_MM:
                    total += step
                    angle = math.degrees(math.atan2(dy, dx)) % 90.0
                    if angle <= AXIS_TOLERANCE_DEG or angle >= 90.0 - AXIS_TOLERANCE_DEG:
                        along += step
            prev = p
    if total < MIN_TRAVEL_MM:
        return None
    return along / total


# ── 2.-4. Rooms ──────────────────────────────────────────────────────────


def _quantile(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * q)))]


def _rectangle(cells: frozenset[Cell]) -> list[float]:
    """[x0, x1, y0, y1) in cells, at the outermost driven floor."""
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return [
        float(_quantile(xs, TRIM)), float(_quantile(xs, 1 - TRIM) + 1),
        float(_quantile(ys, TRIM)), float(_quantile(ys, 1 - TRIM) + 1),
    ]


def _meet_halfway(rects: dict[str, list[float]], max_gap_cells: float) -> None:
    """Facing sides of two rooms closer than a wall plus margins meet."""
    keys = sorted(rects)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            ra, rb = rects[a], rects[b]
            for lo, hi, o0, o1 in ((0, 1, 2, 3), (2, 3, 0, 1)):
                if min(ra[o1], rb[o1]) - max(ra[o0], rb[o0]) < 2:
                    continue  # not facing each other along a stretch
                for p, q in ((ra, rb), (rb, ra)):
                    gap = q[lo] - p[hi]
                    if 0 < gap <= max_gap_cells:
                        mid = float(math.floor((p[hi] + q[lo]) / 2))
                        p[hi] = q[lo] = mid


def _straighten_seams(
    areas: dict[str, frozenset[Cell]], rects: dict[str, list[float]]
) -> None:
    """One straight boundary where two rectangles overlap in a strip.

    The areas meet along a ragged line: which room a cell on the boundary
    went to was the segmentation's call, cell by cell. The two rooms'
    rectangles then overlap by the depth of that raggedness. The wall is
    put through the strip where it cuts the fewest of either room's cells.
    """
    keys = sorted(rects)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            ra, rb = rects[a], rects[b]
            ox0, ox1 = max(ra[0], rb[0]), min(ra[1], rb[1])
            oy0, oy1 = max(ra[2], rb[2]), min(ra[3], rb[3])
            if ox1 <= ox0 or oy1 <= oy0:
                continue
            if ox1 - ox0 <= oy1 - oy0:
                lo, hi, depth, axis = 0, 1, ox1 - ox0, 0
                span = (ox0, ox1)
            else:
                lo, hi, depth, axis = 2, 3, oy1 - oy0, 1
                span = (oy0, oy1)
            if depth > MAX_SEAM_CELLS:
                continue
            # which room lies on the low side of the seam
            low, high = (ra, rb) if ra[lo] + ra[hi] < rb[lo] + rb[hi] else (rb, ra)
            low_key, high_key = (a, b) if low is ra else (b, a)
            best: tuple[int, float] | None = None
            for cut in range(int(span[0]), int(span[1]) + 1):
                wrong = sum(1 for c in areas[low_key] if c[axis] >= cut and span[0] <= c[axis] < span[1])
                wrong += sum(1 for c in areas[high_key] if c[axis] < cut and span[0] <= c[axis] < span[1])
                if best is None or wrong < best[0]:
                    best = (wrong, float(cut))
            if best is not None:
                low[hi] = high[lo] = best[1]


def _cells_of(rect: list[float]) -> set[Cell]:
    return {
        (x, y)
        for x in range(int(rect[0]), int(rect[1]))
        for y in range(int(rect[2]), int(rect[3]))
    }


#: A room's rectangle may take over another room's floor where the two
#: overlap -- a hall's tongue into a doorway, the segmentation's ragged
#: boundary -- but not when it would take more than this share of it:
#: then the two genuinely overlap and the other room keeps its floor.
MAX_TAKEN_SHARE = 0.25


def _place(
    areas: dict[str, frozenset[Cell]], rects: dict[str, list[float]]
) -> dict[str, frozenset[Cell]]:
    """Each room its rectangle, the most rectangular first.

    A rectangle takes the floor of a less rectangular room inside it --
    straight walls win over a ragged boundary -- unless it would take a
    large part of that room (MAX_TAKEN_SHARE). Floor a room drove that
    no other rectangle holds stays its own, whatever the shape.
    """
    def fill(key: str) -> float:
        area = max(1.0, (rects[key][1] - rects[key][0]) * (rects[key][3] - rects[key][2]))
        return len(areas[key]) / area

    boxes = {key: _cells_of(rects[key]) for key in areas}
    owner_of: dict[Cell, str] = {}
    for key, cells in areas.items():
        for c in cells:
            owner_of.setdefault(c, key)
    claimed: set[Cell] = set()
    placed: dict[str, frozenset[Cell]] = {}
    for key in sorted(areas, key=lambda k: (-fill(k), k)):
        box = boxes[key]
        protected = {
            other for other in areas
            if other != key and areas[other]
            and len(areas[other] & box) > MAX_TAKEN_SHARE * len(areas[other])
        }
        mine = {
            c for c in box
            if c not in claimed and owner_of.get(c, key) not in protected
        }
        mine |= {
            c for c in areas[key]
            if c not in claimed
            and not any(c in boxes[k] for k in boxes if k != key)
        }
        placed[key] = frozenset(mine)
        claimed |= mine
    return placed


# ── Walls and doors ──────────────────────────────────────────────────────

#: A unit edge: ("h" or "v", line index, cell along the line).
_Edge = tuple[str, int, int]


def _boundary_edges(rooms: dict[str, frozenset[Cell]]) -> set[_Edge]:
    owner: dict[Cell, str] = {}
    for key, cells in rooms.items():
        for c in cells:
            owner[c] = key
    edges: set[_Edge] = set()
    for (x, y), key in owner.items():
        if owner.get((x + 1, y)) != key:
            edges.add(("v", x + 1, y))
        if owner.get((x - 1, y)) != key:
            edges.add(("v", x, y))
        if owner.get((x, y + 1)) != key:
            edges.add(("h", y + 1, x))
        if owner.get((x, y - 1)) != key:
            edges.add(("h", y, x))
    return edges


def _segments(edges: set[_Edge]) -> list[tuple[str, int, int, int]]:
    """Unit edges joined into straight runs: (orient, line, start, end)."""
    by_line: dict[tuple[str, int], list[int]] = {}
    for orient, line, along in edges:
        by_line.setdefault((orient, line), []).append(along)
    runs: list[tuple[str, int, int, int]] = []
    for (orient, line), alongs in sorted(by_line.items()):
        alongs.sort()
        start = prev = alongs[0]
        for v in alongs[1:]:
            if v == prev + 1:
                prev = v
                continue
            runs.append((orient, line, start, prev + 1))
            start = prev = v
        runs.append((orient, line, start, prev + 1))
    return runs


def _door_shape(
    door: DoorInput, door_mm: float, robot_mm: float
) -> tuple[float, float, bool | None, float, bool]:
    """Centre, whether the door line runs along x (None: not known),
    width and whether it is an open passage."""
    if not door.crossings:
        return door.cx, door.cy, None, door_mm, False
    cx = statistics.median(c[0] for c in door.crossings)
    cy = statistics.median(c[1] for c in door.crossings)
    # Crossed mostly along y: the door line runs along x.
    along_x = sum(abs(c[3]) for c in door.crossings) >= sum(abs(c[2]) for c in door.crossings)
    spread = [c[0] if along_x else c[1] for c in door.crossings]
    measured = max(spread) - min(spread) + robot_mm
    if measured > door_mm + OPEN_EXTRA_MM:
        return cx, cy, along_x, measured, True
    return cx, cy, along_x, door_mm, False


def _cut(
    runs: list[tuple[str, int, int, int]],
    gaps: list[tuple[str, int, float, float]],
) -> list[LayoutWall]:
    """Runs as walls in mm, with the door gaps left open."""
    walls: list[LayoutWall] = []
    for orient, line, start, end in runs:
        pieces = [(start * CELL_MM, end * CELL_MM)]
        for g_orient, g_line, g0, g1 in gaps:
            if g_orient != orient or g_line != line:
                continue
            nxt: list[tuple[float, float]] = []
            for a, b in pieces:
                if g1 <= a or g0 >= b:
                    nxt.append((a, b))
                    continue
                if a < g0:
                    nxt.append((a, g0))
                if g1 < b:
                    nxt.append((g1, b))
            pieces = nxt
        pos = line * CELL_MM
        for a, b in pieces:
            if b - a < CELL_MM / 2:
                continue
            if orient == "h":
                walls.append(LayoutWall(a, pos, b, pos))
            else:
                walls.append(LayoutWall(pos, a, pos, b))
    return walls


def _nearest_run(
    runs: list[tuple[str, int, int, int]], cx: float, cy: float, along_x: bool | None
) -> tuple[float, str, int] | None:
    best: tuple[float, str, int] | None = None
    for orient, line, start, end in runs:
        if along_x is not None and (orient == "h") != along_x:
            continue
        pos, along = (cy, cx) if orient == "h" else (cx, cy)
        if not start * CELL_MM - CELL_MM <= along <= end * CELL_MM + CELL_MM:
            continue
        dist = abs(line * CELL_MM - pos)
        if dist <= DOOR_SNAP_CELLS * CELL_MM and (best is None or dist < best[0]):
            best = (dist, orient, line)
    return best


def _place_doors(
    doors: Sequence[DoorInput],
    runs: list[tuple[str, int, int, int]],
    door_mm: float,
    robot_mm: float,
) -> tuple[list[LayoutDoor], list[tuple[str, int, float, float]], int]:
    placed: list[LayoutDoor] = []
    gaps: list[tuple[str, int, float, float]] = []
    unplaced = 0
    for door in doors:
        cx, cy, along_x, width, is_open = _door_shape(door, door_mm, robot_mm)
        best = _nearest_run(runs, cx, cy, along_x)
        if best is None and along_x is not None:
            # A direction from few crossings can be wrong: any wall close by.
            best = _nearest_run(runs, cx, cy, None)
        if best is None:
            unplaced += 1
            continue
        _dist, orient, line = best
        centre = cx if orient == "h" else cy
        gaps.append((orient, line, centre - width / 2, centre + width / 2))
        if orient == "h":
            placed.append(LayoutDoor(cx, line * CELL_MM, True, width, is_open, door.room_a, door.room_b))
        else:
            placed.append(LayoutDoor(line * CELL_MM, cy, False, width, is_open, door.room_a, door.room_b))
    return placed, gaps, unplaced


# ── Entry point ──────────────────────────────────────────────────────────


def build_layout(
    areas: Sequence[AreaInput],
    doors: Sequence[DoorInput],
    share: float | None,
    wall_mm: float = DEFAULT_WALL_MM,
    door_mm: float = DEFAULT_DOOR_MM,
    robot_mm: float = DEFAULT_ROBOT_DIAMETER_MM,
) -> RoomLayout | None:
    """The layout, or None where walls cannot be taken as straight."""
    if share is None or share < MIN_AXIS_SHARE:
        return None
    rooms_in: dict[str, frozenset[Cell]] = {}
    for area in areas:
        if area.cells:
            rooms_in[area.key] = rooms_in.get(area.key, frozenset()) | area.cells
    if not rooms_in:
        return None
    rects = {key: _rectangle(cells) for key, cells in rooms_in.items()}
    _straighten_seams(rooms_in, rects)
    _meet_halfway(rects, (wall_mm + 2 * CLEAN_MARGIN_MM) / CELL_MM)
    rooms = _place(rooms_in, rects)
    driven = set().union(*rooms_in.values())
    furniture = frozenset(c for cells in rooms.values() for c in cells if c not in driven)
    runs = _segments(_boundary_edges(rooms))
    known = [d for d in doors if d.room_a in rooms and d.room_b in rooms]
    placed, gaps, unplaced = _place_doors(known, runs, door_mm, robot_mm)
    return RoomLayout(
        rooms=rooms,
        walls=tuple(_cut(runs, gaps)),
        doors=tuple(placed),
        furniture=furniture,
        axis_share=share,
        wall_mm=wall_mm,
        door_mm=door_mm,
        unplaced_doors=unplaced,
    )


def _missions(trajectory_store: object) -> list[dict[str, object]]:
    missions = getattr(trajectory_store, "missions", None)
    return missions if isinstance(missions, list) else []


def layout_from_stores(
    room_seg_store: object,
    trajectory_store: object,
    wall_mm: float = DEFAULT_WALL_MM,
    door_mm: float = DEFAULT_DOOR_MM,
    robot_mm: float = DEFAULT_ROBOT_DIAMETER_MM,
) -> RoomLayout | None:
    """The layout from a RoomSegStore and a MissionTrajectoryStore."""
    inputs = getattr(room_seg_store, "layout_inputs", None)
    if not callable(inputs):
        return None
    result = inputs()
    if not (isinstance(result, tuple) and len(result) == 2):
        return None
    areas, doors = result
    share = axis_share(
        m.get("points") or [] for m in _missions(trajectory_store)  # type: ignore[misc]
    )
    return build_layout(areas, doors, share, wall_mm=wall_mm, door_mm=door_mm, robot_mm=robot_mm)


def layout_diagnostics(
    room_seg_store: object,
    trajectory_store: object,
    wall_mm: float = DEFAULT_WALL_MM,
    door_mm: float = DEFAULT_DOOR_MM,
    robot_mm: float = DEFAULT_ROBOT_DIAMETER_MM,
) -> dict[str, object]:
    """Whether a layout is drawn and why not; counts only, no position."""
    share = axis_share(
        m.get("points") or [] for m in _missions(trajectory_store)  # type: ignore[misc]
    )
    layout = layout_from_stores(room_seg_store, trajectory_store, wall_mm, door_mm, robot_mm)
    if layout is None:
        return {
            "drawn": False,
            "axis_share": round(share, 2) if share is not None else None,
            "needs_axis_share": MIN_AXIS_SHARE,
        }
    return {"drawn": True, **layout.diagnostics()}


# ── Room polygons from a cloud map (Smart Map robots, 4.5.0) ─────────────
#
# A Classic robot with a Smart Map gets its rooms from iRobot's own map:
# polygons that are already straight, edited in the app. What the map
# does not draw is walls and doors. Two rooms' polygons touch along the
# divider iRobot puts across the opening between them; everywhere else a
# room's edge faces a wall. So: an edge two rooms share is an opening, a
# door or (much wider than one) an open passage; every other edge is a
# wall; and two wall edges of neighbouring rooms a wall's thickness apart
# are one wall, drawn halfway between.

#: Two edges lie on one line within this distance (mm) and angle (deg).
COLLINEAR_MM = 30.0
PARALLEL_DEG = 3.0
#: Shortest stretch kept as a wall or an opening (mm).
MIN_PIECE_MM = 100.0

Point = tuple[float, float]


@dataclass(frozen=True)
class PolygonWall:
    """A straight wall between two points (mm), any direction."""

    a: Point
    b: Point


@dataclass(frozen=True)
class PolygonOpening:
    """Where two rooms' polygons touch: a door, or an open passage."""

    a: Point
    b: Point
    room_a: str
    room_b: str
    open: bool


@dataclass(frozen=True)
class PolygonWalls:
    walls: tuple[PolygonWall, ...]
    openings: tuple[PolygonOpening, ...]
    wall_mm: float
    door_mm: float

    def diagnostics(self) -> dict[str, object]:
        """Counts and lengths only, no position."""
        return {
            "walls": len(self.walls),
            "wall_length_m": round(
                sum(math.dist(w.a, w.b) for w in self.walls) / 1000, 1
            ),
            "doors": sum(1 for o in self.openings if not o.open),
            "open_passages": sum(1 for o in self.openings if o.open),
            "wall_thickness_mm": self.wall_mm,
            "door_width_mm": self.door_mm,
        }


def _intervals_minus(
    base: tuple[float, float], cuts: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    pieces = [base]
    for c0, c1 in sorted(cuts):
        nxt: list[tuple[float, float]] = []
        for a, b in pieces:
            if c1 <= a or c0 >= b:
                nxt.append((a, b))
                continue
            if a < c0:
                nxt.append((a, c0))
            if c1 < b:
                nxt.append((c1, b))
        pieces = nxt
    return pieces


def _merge_intervals(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


class _Line:
    """One polygon edge as a line: origin, unit direction, length."""

    __slots__ = ("room", "o", "d", "n", "length", "out")

    def __init__(self, room: str, p: Point, q: Point, out: float = 1.0) -> None:
        self.room = room
        #: +1 when `n` points out of the room, -1 when into it.
        self.out = out
        self.o = p
        self.length = math.dist(p, q)
        self.d = ((q[0] - p[0]) / self.length, (q[1] - p[1]) / self.length)
        self.n = (-self.d[1], self.d[0])

    def at(self, t: float, offset: float = 0.0) -> Point:
        return (
            self.o[0] + self.d[0] * t + self.n[0] * offset,
            self.o[1] + self.d[1] * t + self.n[1] * offset,
        )

    def project(self, p: Point) -> tuple[float, float]:
        """(along, across) of a point in this edge's frame."""
        vx, vy = p[0] - self.o[0], p[1] - self.o[1]
        return vx * self.d[0] + vy * self.d[1], vx * self.n[0] + vy * self.n[1]

    def parallel(self, other: _Line) -> bool:
        dot = abs(self.d[0] * other.d[0] + self.d[1] * other.d[1])
        return dot >= math.cos(math.radians(PARALLEL_DEG))


def polygon_walls(
    polygons: Mapping[str, Sequence[Point]],
    wall_mm: float = DEFAULT_WALL_MM,
    door_mm: float = DEFAULT_DOOR_MM,
) -> PolygonWalls:
    """Walls and openings of a map's room polygons (see above)."""
    edges: list[_Line] = []
    for room, poly in polygons.items():
        pts = [(float(x), float(y)) for x, y in poly]
        if len(pts) >= 2 and pts[0] == pts[-1]:
            pts = pts[:-1]
        # Counter-clockwise: the room lies left of each edge, so the left
        # normal points in.
        area2 = sum(
            pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
            for i in range(len(pts))
        )
        out = -1.0 if area2 > 0 else 1.0
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            if math.dist(p, q) >= MIN_PIECE_MM / 2:
                edges.append(_Line(room, p, q, out))

    shared: list[list[tuple[float, float]]] = [[] for _ in edges]
    openings: list[PolygonOpening] = []
    for i, e in enumerate(edges):
        for j, f in enumerate(edges):
            if f.room == e.room or not e.parallel(f):
                continue
            (s0, h0), (s1, h1) = e.project(f.o), e.project(f.at(f.length))
            if abs(h0) > COLLINEAR_MM or abs(h1) > COLLINEAR_MM:
                continue
            # On opposite sides of the line, or it is no divider.
            if (e.n[0] * f.n[0] + e.n[1] * f.n[1]) * e.out * f.out >= 0:
                continue
            lo, hi = max(0.0, min(s0, s1)), min(e.length, max(s0, s1))
            if hi - lo < MIN_PIECE_MM:
                continue
            shared[i].append((lo, hi))
            if e.room < f.room:
                width = hi - lo
                openings.append(PolygonOpening(
                    e.at(lo), e.at(hi), e.room, f.room,
                    open=width > door_mm + OPEN_EXTRA_MM,
                ))

    # Wall pieces: each edge less what it shares.
    pieces: list[tuple[_Line, float, float]] = []
    for e, spans in zip(edges, shared, strict=True):
        for a, b in _intervals_minus((0.0, e.length), _merge_intervals(spans)):
            if b - a >= MIN_PIECE_MM:
                pieces.append((e, a, b))

    # Two rooms' wall pieces a wall apart: one wall, halfway.
    max_gap = wall_mm + 2 * CLEAN_MARGIN_MM
    taken: list[list[tuple[float, float]]] = [[] for _ in pieces]
    walls: list[PolygonWall] = []
    for i, (e, a, b) in enumerate(pieces):
        for j in range(i + 1, len(pieces)):
            f, c, d = pieces[j]
            if f.room == e.room or not e.parallel(f):
                continue
            (s0, h0), (s1, h1) = e.project(f.at(c)), e.project(f.at(d))
            gap = (h0 + h1) / 2
            if not (COLLINEAR_MM < abs(gap) <= max_gap) or abs(h0 - h1) > COLLINEAR_MM:
                continue
            # Facing each other: each lies outside the other room.
            back = f.project(e.at((a + b) / 2))[1]
            if gap * e.out <= 0 or back * f.out <= 0:
                continue
            lo, hi = max(a, min(s0, s1)), min(b, max(s0, s1))
            if hi - lo < MIN_PIECE_MM:
                continue
            walls.append(PolygonWall(e.at(lo, gap / 2), e.at(hi, gap / 2)))
            taken[i].append((lo, hi))
            fl0, fl1 = f.project(e.at(lo))[0], f.project(e.at(hi))[0]
            taken[j].append((min(fl0, fl1), max(fl0, fl1)))
    for (e, a, b), cut in zip(pieces, taken, strict=True):
        for x, y in _intervals_minus((a, b), _merge_intervals(cut)):
            if y - x >= MIN_PIECE_MM:
                walls.append(PolygonWall(e.at(x), e.at(y)))
    return PolygonWalls(tuple(walls), tuple(openings), wall_mm, door_mm)
