"""iRobot's parts catalogue: a how-to link per consumable (4.2.19).

THE MANUFACTURER'S OWN GUIDE, LINKED, NOT REWRITTEN. The iRobot app
shows a replacement guide per part. It comes from a catalogue on the
content host, per robot model and language, without any login:

    GET https://content-prod.iot.irobotapi.com/v2/{lang}/{country}/{sku}/parts
    -> {"buyPartsUrl": ..., "parts": [{"part_id", "part_name",
        "guide_url", "buy_url", ...}]}

The shape is the app's own `AssetPartsDto` / `AssetPartDto`, and the
`part_id` is the one the robot's counters carry -- so a guide joins to
a part sensor by id, on both generations (I4 of the card plan). The
catalogue fills in over time: an id without a guide simply has no
`guide_url` attribute, rather than a made-up one.

Read once per setup, in the background. A failed read costs the links
and nothing else.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import maintenance_changed_signal

_LOGGER = logging.getLogger(__name__)

CATALOGUE_URL = "https://content-prod.iot.irobotapi.com/v2/{lang}/{country}/{sku}/parts"
_TIMEOUT_SECONDS = 15


def catalogue_locale(hass: HomeAssistant) -> tuple[str, str]:
    """`("de-DE", "DE")` from Home Assistant's language and country.

    The path wants a language with region and a country. A bare
    language takes the installation's country as its region; with no
    country set at all, the catalogue's own default (US English).
    """
    language = str(getattr(hass.config, "language", "") or "en")
    country = str(getattr(hass.config, "country", "") or "").upper()
    if "-" in language:
        lang, _, region = language.partition("-")
        country = country or region.upper()
        return f"{lang.lower()}-{region.upper()}", country or "US"
    if not country:
        return "en-US", "US"
    return f"{language.lower()}-{country}", country


def parse_catalogue(payload: Any) -> dict[str, dict[str, str]]:
    """`{part_id: {"guide_url", "buy_url", "part_name", "part_category"}}`,
    each only where the catalogue has it.

    Both spellings of the keys are read: the app's serializer names
    them in snake case, and its envelope already mixes in camel case
    (`buyPartsUrl`).

    The shop link and the category are kept since 4.5.0: the
    maintenance entries link the part to buy, and the name decides a
    Prime part's role (prime_parts.prime_part_role). Images are not --
    nothing of iRobot's is shown, only linked.
    """
    parts = payload.get("parts") if isinstance(payload, dict) else None
    out: dict[str, dict[str, str]] = {}
    for part in parts or []:
        if not isinstance(part, dict):
            continue
        part_id = part.get("part_id", part.get("partId"))
        if part_id is None:
            continue
        entry: dict[str, str] = {}
        for key, camel in (("guide_url", "guideUrl"), ("buy_url", "buyUrl")):
            link = part.get(key) or part.get(camel)
            if isinstance(link, str) and link.startswith("https://"):
                entry[key] = link
        for key, camel in (("part_name", "partName"), ("part_category", "partCategory")):
            text = part.get(key) or part.get(camel)
            if isinstance(text, str) and text:
                entry[key] = text
        if entry:
            out[str(part_id)] = entry
    return out


async def async_fetch_catalogue(
    hass: HomeAssistant, sku: str | None
) -> dict[str, dict[str, str]]:
    """The catalogue for one robot model, or `{}` on any failure."""
    if not sku:
        return {}
    lang, country = catalogue_locale(hass)
    url = CATALOGUE_URL.format(lang=lang, country=country, sku=sku)
    try:
        session = async_get_clientsession(hass)
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
        ) as resp:
            if resp.status != 200:
                _LOGGER.debug("parts catalogue %s: HTTP %s", sku, resp.status)
                return {}
            return parse_catalogue(await resp.json(content_type=None))
    except Exception:  # noqa: BLE001 -- links are enrichment, never a failure
        _LOGGER.debug("parts catalogue %s: could not be read", sku, exc_info=True)
        return {}


async def async_load_into(hass: HomeAssistant, runtime_data: Any, sku: str | None) -> None:
    """Fetch and keep the catalogue on the entry's runtime data.

    The maintenance entries carry its links (4.5.0) and are told when
    it arrives, which is after they were first built."""
    runtime_data.parts_catalogue = await async_fetch_catalogue(hass, sku)
    blid = getattr(runtime_data, "blid", None)
    if runtime_data.parts_catalogue and isinstance(blid, str):
        async_dispatcher_send(hass, maintenance_changed_signal(blid))


def guide_url_for(runtime_data: Any, part_id: Any) -> str | None:
    """The guide link for a part id, if the catalogue has one."""
    if part_id is None:
        return None
    catalogue = getattr(runtime_data, "parts_catalogue", None) or {}
    entry = catalogue.get(str(part_id)) if isinstance(catalogue, dict) else None
    return entry.get("guide_url") if isinstance(entry, dict) else None

