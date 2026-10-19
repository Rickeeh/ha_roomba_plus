"""Care guides: what to do, why, and where on the robot (4.5.0).

ONE PAGE PER TASK, IN THE USER'S LANGUAGE. Each maintenance entry that
has a guide links to it from the maintenance list, the calendar, the
event and -- while the robot reports an error that points to a care
task -- the vacuum's attributes. The page says what the part does, how
to clean or replace it in three or four steps, what not to do, and
shows a drawing of the robot with the part highlighted. iRobot's own
guide for the model is linked below it where the parts catalogue has
one.

WRITTEN AND DRAWN FOR THIS PROJECT (AGENTS.md rule 8). The texts are in
`care/texts/<language>.json`, one file per language with the
same keys and the same number of steps; the drawings in
`care/schemata/` are plain SVG with one group per part
(`part-<name>`) and one numbered marker per part (`m-<name>`). Nothing
is highlighted in the file: the page adds a style that colours the
part, puts a halo round it -- so it does not rest on colour alone --
and shows its marker. The drawings follow the reader's light or dark
mode.

THE LINK IS SIGNED, NOT AUTHENTICATED. A link in a to-do description or
a notification is opened by the browser without Home Assistant's
access token, so the views do not require one. They answer only a path
signed with this installation's own secret (HMAC-SHA256, kept in
`.storage/roomba_plus.care_guides`, never logged or put in
diagnostics). The signature covers the entry, the guide, the language
and the expiry. The page holds nothing private: the guide text, the
drawing for the robot's series and iRobot's public link.

THE EXPIRY MOVES ONCE A WEEK. Home Assistant's own signed paths carry
the moment they were signed, so every recompute would change every
description. Here the expiry is a day number, the start of the week
plus 37 days: a link is valid for 31 to 37 days, and a description
changes at most once a week. An expired link says where to get a new
one, in the language it was made for.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
import re
import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .models import ConnectionType

_LOGGER = logging.getLogger(__name__)

_DIR = Path(__file__).parent / "care"
#: The languages with care texts; anything else reads English.
LANGUAGES: tuple[str, ...] = ("en", "de", "fr", "es", "it", "nl", "pl", "pt")
DEFAULT_LANGUAGE = "en"

GUIDE_URL = "/api/roomba_plus/care/{entry_id}/{guide}"
#: Every guide as a page on GitHub, made from these texts and drawings by
#: scripts/build_care_docs.py: where an expired link sends the reader.
CARE_DOCS_URL = "https://github.com/johnnyh1975/ha_roomba_plus/blob/main/docs/care/{lang}/README.md"
SCHEMA_URL = "/api/roomba_plus/care/{entry_id}/{guide}/schema.svg"

_DATA_KEY = f"{DOMAIN}_care_guides"
_STORE_KEY = f"{DOMAIN}.care_guides"
_STORE_VERSION = 1

#: A link is valid from the start of its week for this many days.
_LIFETIME_DAYS = 37
_WEEK_DAYS = 7

#: Each guide's drawings and the part each highlights. "underside",
#: "bin" and "dock" follow the robot (`RobotContext`); the others are
#: the same everywhere. The charging contacts show the robot and its
#: dock. The camera has no drawing: every series has it somewhere else.
GUIDE_SCHEMATA: dict[str, tuple[tuple[str, str], ...]] = {
    "clean_filter": (("bin", "filter"),),
    "replace_filter": (("bin", "filter"),),
    "clean_bin": (("bin", "bin"),),
    "clean_brushes": (("underside", "main_brush"),),
    "replace_main_brush": (("underside", "main_brush"),),
    "clean_side_brush": (("underside", "side_brush"),),
    "replace_side_brush": (("underside", "side_brush"),),
    "clean_wheel": (("underside", "wheel"),),
    "clean_cliff_sensors": (("underside", "cliff_sensors"),),
    "clean_contact": (("underside", "contact"), ("dock", "contact")),
    "replace_battery": (("underside", "battery"),),
    "replace_pad": (("underside", "pad"),),
    "replace_bag": (("clean_base", "bag"),),
    "clean_wash_dock": (("wash_dock", "water_tanks"),),
    "clean_dock_washing_system": (("wash_dock", "dock_washing_system"),),
    "clean_mop_washing_system": (("wash_dock", "mop_washing_system"),),
    "replace_roller": (("wash_dock", "roller"),),
    "replace_detergent": (("wash_dock", "detergent"),),
}
#: Guides without a drawing.
GUIDES_WITHOUT_SCHEMA: frozenset[str] = frozenset({"clean_camera"})
GUIDES: tuple[str, ...] = (*GUIDE_SCHEMATA, *sorted(GUIDES_WITHOUT_SCHEMA))

#: Parts whose name differs from their guide's.
_CLEAN_ALIASES: dict[str, str] = {
    "main_brush": "brushes",
    "sensor": "cliff_sensors",
}
_REPLACE_ALIASES: dict[str, str] = {
    "clean_base_bag": "replace_bag",
    "bag": "replace_bag",
    # A Prime robot's own counters for jobs, not parts: cleaning guides.
    "sensor": "clean_cliff_sensors",
    "dock_washing_system": "clean_dock_washing_system",
    "mop_washing_system": "clean_mop_washing_system",
}
#: A cleaning guide's replacement twin, for iRobot's link: the parts
#: catalogue has guides for parts, not for care tasks.
_TWINS: dict[str, str] = {
    "clean_filter": "replace_filter",
    "clean_brushes": "replace_main_brush",
    "clean_side_brush": "replace_side_brush",
}

#: The highlight. Light mode: amber fill, dark outline and a pale amber
#: halo. Dark mode keeps the amber and turns what is drawn as a line
#: off the part's fill -- the side brush's arms and bristles, the
#: filter's arrow -- pale, so it does not vanish on a dark background.
_HIGHLIGHT = (
    "<style>"
    "#part-{p} .pt,#part-{p} .lt,#part-{p} .body{{fill:#FFB000;stroke:#7A4E00;stroke-width:3}}"
    "#part-{p} .fine,#part-{p} .ln{{stroke:#7A4E00}}"
    "#part-{p} .hal{{display:inline}}#m-{p}{{display:inline}}"
    "@media (prefers-color-scheme:dark){{"
    "#part-{p} .pt,#part-{p} .lt,#part-{p} .body{{fill:#FFB000;stroke:#FFE7A8}}"
    "#part-{p} .fine{{stroke:#5A3A00}}"
    "#part-{p} .ln,#part-{p} .brs{{stroke:#FFE7A8}}}}"
    "</style>"
)
_TITLE = re.compile(r"<title>.*?</title>", re.S)


# ── Which guide, which drawing ──────────────────────────────────────────────

def guide_id(action: str, part: str) -> str | None:
    """The guide for a maintenance entry, by its action and part."""
    if action == "replace":
        key = _REPLACE_ALIASES.get(part, f"replace_{part}")
    elif action in ("clean", "check"):
        key = f"clean_{_CLEAN_ALIASES.get(part, part)}"
    else:
        return None
    return key if key in GUIDES else None


@dataclass(frozen=True)
class RobotContext:
    """What a guide needs to know about the robot.

    `series` picks the text: the 600, the 800/900, the e/i/j and the s
    series empty their bins, release their brushes and fasten their
    side brush differently. None reads the general text -- a Prime robot,
    whose parts iRobot's articles do not describe per model yet.
    `underside` and `bin` pick the drawings, `dock` the dock's text and
    drawing for the charging contacts."""

    series: str | None = None
    underside: str = "eij"
    bin: str = "eij"
    dock: str = "home_base"


GENERIC = RobotContext()
DOCKS: tuple[str, ...] = ("home_base", "clean_base", "wash_dock")


def series_for(sku: Any, prime: bool) -> str | None:
    """The text series of a Classic robot by its SKU: "600" (600 and
    700), "900" (800 and 900), "eij" (e, i, j and Combo j), "s",
    "braava"; None for a Prime robot or an SKU not known here."""
    if prime or not isinstance(sku, str) or not sku:
        return None
    first = sku[0].lower()
    if first == "r" and len(sku) > 1:
        first = sku[1]
    if first in ("6", "7"):
        return "600"
    if first in ("8", "9"):
        return "900"
    if first in ("e", "i", "j", "c"):
        return "eij"
    if first == "s":
        return "s"
    if first == "m":
        return "braava"
    return None


def robot_context(sku: Any, prime: bool, dock: str = "home_base") -> RobotContext:
    """The guide context of a robot. A Prime robot and anything unknown
    draws the e/i/j underside and bin: every Prime model has two rubber
    rollers."""
    series = series_for(sku, prime)
    underside = {"600": "600_900", "900": "600_900", "s": "s", "braava": "braava"}
    bins = {"600": "600_900", "900": "600_900", "s": "s"}
    return RobotContext(
        series=series,
        underside=underside.get(series or "", "eij"),
        bin=bins.get(series or "", "eij"),
        dock=dock if dock in DOCKS else "home_base",
    )


def variant_for(sku: Any, prime: bool) -> str:
    """The underside drawing for a robot: 600-900 (one bristle and one
    rubber brush), e/i/j (two rubber rollers), s or Braava."""
    return robot_context(sku, prime).underside


def schema_names(guide: str, ctx: RobotContext = GENERIC) -> list[tuple[str, str]]:
    """The drawings' file stems and the part each highlights."""
    out: list[tuple[str, str]] = []
    for kind, part in GUIDE_SCHEMATA.get(guide, ()):
        if kind == "underside":
            stem = f"underside_{ctx.underside}"
        elif kind == "bin":
            stem = f"bin_{ctx.bin}"
        elif kind == "dock":
            stem = ctx.dock
        else:
            stem = kind
        out.append((stem, part))
    return out


def highlight(svg: str, part: str, title: str | None = None) -> str:
    """The drawing with `part` highlighted and its title replaced."""
    if title is not None:
        svg = _TITLE.sub(f"<title>{html.escape(title)}</title>", svg, count=1)
    return svg.replace("</svg>", _HIGHLIGHT.format(p=part) + "</svg>", 1)


def language_for(language: Any) -> str:
    """One of LANGUAGES for a Home Assistant language: "pt-BR" is "pt"."""
    if not isinstance(language, str):
        return DEFAULT_LANGUAGE
    base = language.replace("_", "-").split("-", 1)[0].lower()
    return base if base in LANGUAGES else DEFAULT_LANGUAGE


# ── Signing ─────────────────────────────────────────────────────────────────

def _epoch_day(now: datetime) -> int:
    return int(now.timestamp() // 86400)


def expiry_day(now: datetime) -> int:
    """The link's last day + 1, as days since 1970: the start of the
    week plus `_LIFETIME_DAYS`, so it holds for a week of signing."""
    day = _epoch_day(now)
    return day - day % _WEEK_DAYS + _LIFETIME_DAYS


def _signature(secret: bytes, entry_id: str, guide: str, lang: str, exp: int) -> str:
    message = f"{entry_id}\n{guide}\n{lang}\n{exp}".encode()
    digest = hmac.new(secret, message, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


class CareGuides:
    """The texts, the drawings and the secret, once per installation."""

    def __init__(
        self,
        secret: bytes,
        texts: Mapping[str, Mapping[str, Any]],
        schemata: Mapping[str, str],
    ) -> None:
        self._secret = secret
        self._texts = texts
        self._schemata = schemata

    # ── links ──

    def query(self, entry_id: str, guide: str, lang: str, now: datetime | None = None) -> str:
        exp = expiry_day(now or dt_util.utcnow())
        return urlencode({
            "lang": lang,
            "exp": exp,
            "sig": _signature(self._secret, entry_id, guide, lang, exp),
        })

    def page_path(
        self, entry_id: str, guide: str, lang: str, now: datetime | None = None,
    ) -> str | None:
        if guide not in GUIDES:
            return None
        path = GUIDE_URL.format(entry_id=entry_id, guide=guide)
        return f"{path}?{self.query(entry_id, guide, lang, now)}"

    def schema_path(
        self, entry_id: str, guide: str, lang: str, now: datetime | None = None, n: int = 0,
    ) -> str | None:
        """The signed path of the guide's drawing number `n` (from 0).
        `n` is outside the signature: it only picks one of the guide's
        own drawings."""
        if guide not in GUIDE_SCHEMATA:
            return None
        path = SCHEMA_URL.format(entry_id=entry_id, guide=guide)
        extra = f"&n={n}" if n else ""
        return f"{path}?{self.query(entry_id, guide, lang, now)}{extra}"

    def check(
        self, entry_id: str, guide: str, query: Mapping[str, str],
        now: datetime | None = None,
    ) -> str:
        """"ok", "expired", or "bad" for anything not signed here."""
        lang = query.get("lang", "")
        try:
            exp = int(query.get("exp", ""))
        except ValueError:
            return "bad"
        expected = _signature(self._secret, entry_id, guide, lang, exp)
        if guide not in GUIDES or not hmac.compare_digest(expected, query.get("sig", "")):
            return "bad"
        if _epoch_day(now or dt_util.utcnow()) >= exp:
            return "expired"
        return "ok"

    # ── content ──

    def text(self, lang: str) -> Mapping[str, Any]:
        return self._texts.get(lang) or self._texts.get(DEFAULT_LANGUAGE) or {}

    def guide(
        self, guide: str, lang: str, ctx: RobotContext | None = None,
    ) -> Mapping[str, Any]:
        """The guide's texts, with the robot's series and dock variant
        laid over the general text where the guide has one."""
        found = self.text(lang).get(guide)
        if not isinstance(found, Mapping):
            found = self.text(DEFAULT_LANGUAGE).get(guide)
        if not isinstance(found, Mapping):
            return {}
        merged = {k: v for k, v in found.items() if k != "variants"}
        variants = found.get("variants")
        if ctx is not None and isinstance(variants, Mapping):
            for key in (ctx.series, ctx.dock):
                if key is not None and isinstance(variants.get(key), Mapping):
                    merged.update(variants[key])
        return merged

    def title(self, guide: str, lang: str, ctx: RobotContext | None = None) -> str:
        return str(self.guide(guide, lang, ctx).get("title") or guide)

    def schema_svgs(self, guide: str, ctx: RobotContext, lang: str) -> list[str]:
        """The guide's drawings for this robot, highlighted -- without a
        drawing that lacks the part (a Prime Combo's pad is not on the
        e/i/j underside)."""
        title = self.title(guide, lang, ctx)
        out: list[str] = []
        for stem, part in schema_names(guide, ctx):
            svg = self._schemata.get(stem)
            if svg is not None and f'id="part-{part}"' in svg:
                out.append(highlight(svg, part, title))
        return out

    def schema_svg(
        self, guide: str, ctx: RobotContext, lang: str, n: int = 0,
    ) -> str | None:
        svgs = self.schema_svgs(guide, ctx, lang)
        return svgs[n] if 0 <= n < len(svgs) else None

    def pictures_markdown(
        self, entry_id: str, guide: str, ctx: RobotContext, lang: str,
    ) -> str:
        """Markdown images of the guide's drawings, signed, for a form."""
        title = self.title(guide, lang, ctx)
        return "\n\n".join(
            f"![{title}]({self.schema_path(entry_id, guide, lang, n=n)})"
            for n in range(len(self.schema_svgs(guide, ctx, lang)))
        )

    def markdown(
        self,
        guide: str,
        lang: str,
        picture: str | None = None,
        ctx: RobotContext | None = None,
        when: str | None = None,
    ) -> str:
        """The guide as Markdown, for a form's description."""
        page = self.text(lang).get("_page") or {}
        g = self.guide(guide, lang, ctx)
        steps = "\n".join(f"{n}. {s}" for n, s in enumerate(g.get("steps") or [], 1))
        parts = [
            picture or "",
            f"**{page.get('why', '')}**  \n{g.get('why', '')}",
            f"**{page.get('when', '')}**  \n{when}" if when else "",
            f"**{page.get('how', '')}**\n\n{steps}",
            f"**{page.get('note', '')}**  \n{g.get('caution', '')}",
        ]
        return "\n\n".join(p for p in parts if p)

    def page(
        self,
        guide: str,
        lang: str,
        ctx: RobotContext = GENERIC,
        irobot_url: str | None = None,
        when: str | None = None,
    ) -> str:
        page = self.text(lang).get("_page") or {}
        g = self.guide(guide, lang, ctx)
        e = html.escape
        steps = "".join(f"<li>{e(str(s))}</li>" for s in g.get("steps") or [])
        pictures = "".join(f'<div class="pic">{svg}</div>' for svg in self.schema_svgs(guide, ctx, lang))
        link = (
            f'<p class="more"><a href="{e(irobot_url)}" rel="noreferrer noopener">'
            f"{e(str(page.get('irobot', '')))}</a></p>"
            if irobot_url else ""
        )
        title = self.title(guide, lang, ctx)
        body = (
            f"<h1>{e(title)}</h1>"
            + pictures
            + f"<h2>{e(str(page.get('why', '')))}</h2><p>{e(str(g.get('why', '')))}</p>"
            # "When", as the dialog has it (4.5.0b2): interval, what is
            # left, the last time -- at the time the page is opened.
            + (f"<h2>{e(str(page.get('when', '')))}</h2><p>{e(when)}</p>" if when else "")
            + f"<h2>{e(str(page.get('how', '')))}</h2><ol>{steps}</ol>"
            + f'<div class="note"><strong>{e(str(page.get("note", "")))}</strong> '
            + f"{e(str(g.get('caution', '')))}</div>"
            + link
        )
        return _document(lang, title, body)

    def notice(self, lang: str, kind: str) -> str:
        """The page for an expired or unknown link."""
        page = self.text(lang).get("_page") or {}
        title = str(page.get(f"{kind}_title", ""))
        text = str(page.get(f"{kind}_text", ""))
        e = html.escape
        docs = (
            f'<p class="more"><a href="{e(CARE_DOCS_URL.format(lang=lang))}" '
            f'rel="noreferrer noopener">{e(str(page["docs"]))}</a></p>'
            if page.get("docs") else ""
        )
        return _document(lang, title, f"<h1>{e(title)}</h1><p>{e(text)}</p>{docs}")


_CSS = (
    ":root{color-scheme:light dark;--fg:#1F2933;--bg:#FFFFFF;--muted:#52606D;"
    "--note:#FFF4D6;--line:#E4E7EB;--link:#0B63B5}"
    "@media (prefers-color-scheme:dark){:root{--fg:#E4E7EB;--bg:#111417;"
    "--muted:#A9B4BF;--note:#3A2E10;--line:#2B3138;--link:#7CB8F0}}"
    "body{margin:0;background:var(--bg);color:var(--fg);"
    "font:16px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}"
    "main{max-width:640px;margin:0 auto;padding:16px}"
    "h1{font-size:1.5rem;margin:.5rem 0 1rem}"
    "h2{font-size:1.05rem;margin:1.25rem 0 .25rem;color:var(--muted)}"
    ".pic{max-width:360px;margin:0 auto 12px}.pic svg{width:100%;height:auto;display:block}"
    "ol{padding-left:1.4rem}li{margin:.35rem 0}"
    ".note{background:var(--note);border-radius:8px;padding:12px 14px;margin:1.25rem 0}"
    ".more{border-top:1px solid var(--line);padding-top:12px}a{color:var(--link)}"
)


def _document(lang: str, title: str, body: str) -> str:
    return (
        f'<!doctype html><html lang="{html.escape(lang)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex">'
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )


# ── Loading ─────────────────────────────────────────────────────────────────

def _read_files() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    texts: dict[str, dict[str, Any]] = {}
    for lang in LANGUAGES:
        path = _DIR / "texts" / f"{lang}.json"
        if path.is_file():
            texts[lang] = json.loads(path.read_text(encoding="utf-8"))
    schemata = {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted((_DIR / "schemata").glob("*.svg"))
    }
    return texts, schemata


async def async_setup_care_guides(hass: HomeAssistant) -> CareGuides | None:
    """Load the guides and the secret once, and register the views.

    A failure costs the links only: every surface leaves them out while
    `get_care_guides` answers None."""
    if (existing := get_care_guides(hass)) is not None:
        return existing
    try:
        store: Store[dict[str, Any]] = Store(hass, _STORE_VERSION, _STORE_KEY, private=True)
        stored = await store.async_load() or {}
        secret_hex = stored.get("secret")
        if not isinstance(secret_hex, str) or len(secret_hex) < 64:
            secret_hex = secrets.token_hex(32)
            await store.async_save({"secret": secret_hex})
        texts, schemata = await hass.async_add_executor_job(_read_files)
    except Exception:  # noqa: BLE001 -- the guides are optional
        _LOGGER.warning("Roomba+: the care guides could not be loaded", exc_info=True)
        return None
    if (existing := get_care_guides(hass)) is not None:
        return existing  # a second robot's setup got here first
    guides = CareGuides(bytes.fromhex(secret_hex), texts, schemata)
    hass.data[_DATA_KEY] = guides
    http = getattr(hass, "http", None)
    if http is not None:
        http.register_view(CareGuidePageView())
        http.register_view(CareGuideSchemaView())
    return guides


def get_care_guides(hass: Any) -> CareGuides | None:
    data = getattr(hass, "data", None)
    found = data.get(_DATA_KEY) if isinstance(data, dict) else None
    return found if isinstance(found, CareGuides) else None


def page_anchor(path: str, text: str) -> str:
    """A link to a guide page for Home Assistant's Markdown -- as HTML,
    with `target="_blank"`.

    A Markdown link to a path on Home Assistant's own host is taken over
    by the frontend's router: a click in a dialog, the to-do list or a
    repair issue went to the overview instead of the page (seen 18.10.
    in the options dialog). The frontend's handler for same-origin links
    skips an anchor that has a target, and its Markdown sanitizer keeps
    `target`, `href` and `title` on `a` (checked in the frontend build).
    A link to another host gets its target from the frontend already."""
    return (
        f'<a href="{html.escape(path, quote=True)}" target="_blank">'
        f"{html.escape(text, quote=False)}</a>"
    )


def guide_link(hass: Any, entry_id: str, guide: str | None) -> str | None:
    """The signed page path for a guide in Home Assistant's language,
    relative -- it opens in the browser and in the companion app alike,
    and carries no address."""
    guides = get_care_guides(hass)
    if guides is None or guide is None:
        return None
    lang = language_for(getattr(getattr(hass, "config", None), "language", None))
    return guides.page_path(entry_id, guide, lang)


def _hass_language(hass: Any) -> str:
    return language_for(getattr(getattr(hass, "config", None), "language", None))


def guide_title(hass: Any, guide: str | None) -> str | None:
    """The guide's title in Home Assistant's language -- "Filter
    reinigen" -- for a notification that should not read "clean.filter"."""
    guides = get_care_guides(hass)
    if guides is None or guide is None:
        return None
    return guides.title(guide, _hass_language(hass))


def guide_why(hass: Any, guide: str | None, ctx: RobotContext | None = None) -> str | None:
    """The guide's "what it does" sentence in Home Assistant's language,
    for the maintenance list and calendar."""
    guides = get_care_guides(hass)
    if guides is None or guide is None:
        return None
    why = guides.guide(guide, _hass_language(hass), ctx).get("why")
    return str(why) if why else None


def context_for(data: Any) -> RobotContext:
    """The guide context of a loaded robot: its series from the SKU
    (Classic), its dock from the parts it has -- a wash dock where it has
    washing systems, a Clean Base where it has a bag, else a Home Base."""
    if data is None:
        return GENERIC
    prime = getattr(data, "connection_type", None) is ConnectionType.CLOUD_ONLY
    sku = None
    if not prime:
        try:
            sku = data.roomba_reported_state().get("sku")
        except Exception:  # noqa: BLE001 -- no state yet: the general text
            sku = None
    tracker = getattr(data, "maintenance", None)
    parts = {getattr(i, "part", None) for i in (tracker.items if tracker is not None else [])}
    if parts & {"dock_washing_system", "mop_washing_system", "wash_dock"}:
        dock = "wash_dock"
    elif parts & {"clean_base_bag", "bag"}:
        dock = "clean_base"
    else:
        dock = "home_base"
    return robot_context(sku, prime, dock)


def guide_entry(items: Iterable[Any], guide: str) -> Any:
    """The maintenance entry a guide belongs to: its care task before its
    replacement, as the cleaning guide of a part is the task's."""
    entries = [i for i in items if getattr(i, "guide_id", None) == guide]
    return next(
        (i for i in entries if getattr(i, "action", None) != "replace"),
        entries[0] if entries else None,
    )


def _entry_item(hass: HomeAssistant, entry_id: str, guide: str) -> Any:
    """The robot's maintenance entry for this guide, None for an entry
    that is gone or a guide without one."""
    entry = hass.config_entries.async_get_entry(entry_id)
    data = getattr(entry, "runtime_data", None) if entry is not None and entry.domain == DOMAIN else None
    tracker = getattr(data, "maintenance", None)
    return guide_entry(tracker.items, guide) if tracker is not None else None


def _entry_context(
    hass: HomeAssistant, entry_id: str, guide: str,
) -> tuple[RobotContext, str | None]:
    """The robot's guide context and iRobot's guide link, from its entry
    -- the general text and no link for an entry that is gone."""
    entry = hass.config_entries.async_get_entry(entry_id)
    data = getattr(entry, "runtime_data", None) if entry is not None and entry.domain == DOMAIN else None
    if data is None:
        return GENERIC, None
    tracker = getattr(data, "maintenance", None)
    items = tracker.items if tracker is not None else []
    return context_for(data), irobot_link(items, guide)


# ── Wording from the translations ───────────────────────────────────────────

#: The maintenance item wording in English, used where the translation
#: table cannot be read. Keys match `selector.maintenance_item.options`
#: in strings.json (a test holds them equal).
ENGLISH_WORDING: dict[str, str] = {
    "replace_filter": "Replace the filter",
    "replace_main_brushes": "Replace the main brushes",
    "replace_mop_pad": "Replace the mop pad",
    "replace_side_brush": "Replace the side brush",
    "replace_clean_base_bag": "Replace the Clean Base bag",
    "replace_dust_bag": "Replace the dust bag",
    "replace_detergent": "Replace the detergent",
    "replace_roller": "Replace the roller mop",
    "replace_battery": "Replace the battery",
    "replace_part": "Replace: {part}",
    "clean_filter": "Clean the filter",
    "clean_brushes": "Clean the main brushes",
    "clean_side_brush": "Clean the side brush",
    "clean_wheel": "Clean the wheels",
    "clean_cliff_sensors": "Clean the cliff sensors",
    "clean_contact": "Clean the charging contacts",
    "clean_mop_washing_system": "Clean the mop washing system",
    "clean_dock_washing_system": "Clean the dock washing system",
    "clean_part": "Clean: {part}",
    "check_filter": "Check the filter",
    "check_brushes": "Check the main brushes",
    "check_side_brush": "Check the side brush",
    "check_wheel": "Check the wheels",
    "check_cliff_sensors": "Check the cliff sensors",
    "check_contact": "Check the charging contacts",
    "check_bin": "Check the bin",
    "check_camera": "Check the camera window",
    "check_wash_dock": "Check the wash dock",
    "every_days": "Every {days} days, as iRobot recommends.",
    "left": "{value} {unit} left",
    "unit_hours": "hours",
    "unit_days": "days",
    "unit_missions": "missions",
    "unit_evacuations": "dust collections",
    "unit_pad_washes": "pad washes",
    "unit_charge_cycles": "charge cycles",
    "unit_sqft": "ft²",
    "error_line": "The robot reports error {code}.",
    "reason_cliff": "The robot will not start: it sees a drop.",
    "reason_brush_stall": "The robot will not start: a brush is stuck.",
    "reason_no_bin": "The robot will not start: the bin is missing.",
    "reason_bin_full": "The bin is full.",
    "reason_camera": "The robot will not start: its camera does not respond.",
    "interval_line": "Interval {value} {unit}, {source}",
    "source_cloud": "from the robot's counter",
    "source_learned": "learned from your replacements",
    "source_configured": "set by you",
    "source_profile": "from the series profile",
    "source_irobot_budget": "iRobot's figure",
    "source_calendar": "on the care calendar",
    "last_done": "Last done {date}",
    "estimate_note": "Estimated from the wear rate; the date moves with every run.",
    "part_main_brush": "main brushes",
    "part_side_brush": "side brush",
    "part_filter": "filter",
    "part_bag": "dust bag",
    "part_pad": "mop pad",
    "part_detergent": "detergent",
    "part_roller": "roller mop",
    "part_battery": "battery",
    "part_sensor": "cliff sensors",
    "part_mop_washing_system": "mop washing system",
    "part_dock_washing_system": "dock washing system",
    "link_care_guide": "How to do it",
    "link_guide": "iRobot's guide",
    "link_buy": "Buy the part",
    "reconfigure_rooms": "Name the rooms",
    "reconfigure_rooms_description": (
        "Some rooms have no name yet. Open Configure → Rooms & zones: it "
        "shows the robot's map with their numbers, or says what is missing. "
        "This item clears itself once every room has a name."
    ),
    "overview_item": "Part or task",
    "overview_level": "Status",
    "overview_left": "Left",
    "overview_source": "Interval",
}


async def async_wording(hass: HomeAssistant, language: str | None = None) -> dict[str, str]:
    """The maintenance item wording (`selector.maintenance_item`) in Home
    Assistant's language -- or in `language`, a guide page's -- Home
    Assistant filling gaps from English."""
    try:
        table = await async_get_translations(
            hass, language or hass.config.language, "selector", {DOMAIN},
        )
    except Exception:  # noqa: BLE001 -- English then
        table = {}
    prefix = f"component.{DOMAIN}.selector.maintenance_item.options."
    return {
        **ENGLISH_WORDING,
        **{k[len(prefix):]: v for k, v in table.items() if k.startswith(prefix) and isinstance(v, str)},
    }


def _fmt(value: Any) -> str:
    return f"{float(value):g}"


def interval_text(item: Any, wording: Mapping[str, str]) -> str | None:
    """"Interval 52 hours, from the series profile" -- or None."""
    if item is None or getattr(item, "interval", None) is None:
        return None
    unit = getattr(item, "interval_unit", None) or ""
    source = getattr(item, "interval_source", None) or ""
    template = wording.get("interval_line")
    if not template:
        return None
    return (
        template.replace("{value}", _fmt(item.interval))
        .replace("{unit}", wording.get(f"unit_{unit}", unit))
        .replace("{source}", wording.get(f"source_{source}", source))
    )


def when_text(item: Any, wording: Mapping[str, str]) -> str | None:
    """The guide's "When": the interval and its source, what is left and
    when it was last done, from the robot's maintenance entry."""
    if item is None:
        return None
    lines: list[str] = []
    interval = interval_text(item, wording)
    if interval:
        lines.append(interval)
    remaining = getattr(item, "remaining", None)
    unit = getattr(item, "unit", None)
    if remaining is not None and unit and wording.get("left"):
        lines.append(
            wording["left"].replace("{value}", _fmt(remaining))
            .replace("{unit}", wording.get(f"unit_{unit}", unit))
        )
    last = getattr(item, "last_done", None)
    if last and wording.get("last_done"):
        parsed = dt_util.parse_datetime(str(last))
        date = dt_util.as_local(parsed).date().isoformat() if parsed else str(last)[:10]
        lines.append(wording["last_done"].replace("{date}", date))
    return " · ".join(lines) or None


def irobot_link(items: Iterable[Any], guide: str) -> str | None:
    """iRobot's guide link for this guide: the entry's own, else its
    replacement twin's. Only https links are passed on."""
    wanted = [guide, *([_TWINS[guide]] if guide in _TWINS else [])]
    entries = list(items)
    for key in wanted:
        for item in entries:
            url = getattr(item, "guide_url", None)
            if (
                getattr(item, "guide_id", None) == key
                and isinstance(url, str)
                and url.startswith("https://")
            ):
                return url
    return None


# ── Views ───────────────────────────────────────────────────────────────────

_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "private, max-age=3600",
}


class CareGuidePageView(HomeAssistantView):
    """GET /api/roomba_plus/care/{entry_id}/{guide}?lang=&exp=&sig=

    No access token: the signature is the access (module docstring)."""

    url = GUIDE_URL
    name = "api:roomba_plus:care_guide"
    requires_auth = False

    async def get(self, request: web.Request, entry_id: str, guide: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        guides = get_care_guides(hass)
        if guides is None:
            return web.Response(status=404)
        lang = language_for(request.query.get("lang"))
        verdict = guides.check(entry_id, guide, request.query)
        if verdict != "ok":
            status = 410 if verdict == "expired" else 404
            kind = "expired" if verdict == "expired" else "unknown"
            return _html(guides.notice(lang, kind), status)
        ctx, irobot = _entry_context(hass, entry_id, guide)
        when = when_text(_entry_item(hass, entry_id, guide), await async_wording(hass, lang))
        return _html(guides.page(guide, lang, ctx, irobot, when), 200)


class CareGuideSchemaView(HomeAssistantView):
    """GET /api/roomba_plus/care/{entry_id}/{guide}/schema.svg?... --
    the drawing alone, for the guide form in Configure → Maintenance."""

    url = SCHEMA_URL
    name = "api:roomba_plus:care_guide_schema"
    requires_auth = False

    async def get(self, request: web.Request, entry_id: str, guide: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        guides = get_care_guides(hass)
        if guides is None or guides.check(entry_id, guide, request.query) != "ok":
            return web.Response(status=404)
        ctx, _irobot = _entry_context(hass, entry_id, guide)
        try:
            n = int(request.query.get("n", "0"))
        except ValueError:
            n = 0
        svg = guides.schema_svg(guide, ctx, language_for(request.query.get("lang")), n)
        if svg is None:
            return web.Response(status=404)
        return web.Response(
            text=svg, content_type="image/svg+xml", charset="utf-8", headers=_HEADERS,
        )


def _html(document: str, status: int) -> web.Response:
    return web.Response(
        text=document, status=status, content_type="text/html", charset="utf-8",
        headers=_HEADERS,
    )
