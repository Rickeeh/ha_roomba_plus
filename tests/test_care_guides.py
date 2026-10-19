"""Tests for care_guides.py: texts, drawings, signed links, the views."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.roomba_plus import care_guides as cg

PKG = Path(__file__).resolve().parent.parent / "custom_components" / "roomba_plus"
_NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _texts() -> dict[str, dict]:
    return {
        lang: json.loads((PKG / "care" / "texts" / f"{lang}.json").read_text(encoding="utf-8"))
        for lang in cg.LANGUAGES
    }


def _guides() -> cg.CareGuides:
    texts, schemata = cg._read_files()
    return cg.CareGuides(b"s" * 32, texts, schemata)


def base_caution(guides):
    return guides.guide("clean_contact", "en")["caution"]


class TestTheTexts:

    def test_every_language_has_every_guide_with_the_same_steps(self):
        texts = _texts()
        en = texts["en"]
        assert set(en) == {"_page", *cg.GUIDES}
        for lang, doc in texts.items():
            assert set(doc) == set(en), lang
            assert set(doc["_page"]) == set(en["_page"]), lang
            for guide in cg.GUIDES:
                g = doc[guide]
                assert set(g) - {"variants"} == {"title", "why", "steps", "caution"}, (lang, guide)
                assert len(g["steps"]) == len(en[guide]["steps"]), (lang, guide)
                assert all(isinstance(s, str) and s.strip() for s in g["steps"]), (lang, guide)
                assert g["title"].strip() and g["why"].strip() and g["caution"].strip()

    def test_every_language_has_every_variant_with_the_same_steps(self):
        """A variant -- the robot's series or dock -- overrides some of
        its guide's fields; every language overrides the same ones."""
        texts = _texts()
        keys = {"600", "900", "eij", "s", "braava", *cg.DOCKS}
        for guide in cg.GUIDES:
            variants = texts["en"][guide].get("variants", {})
            assert set(variants) <= keys, guide
            for lang, doc in texts.items():
                theirs = doc[guide].get("variants", {})
                assert set(theirs) == set(variants), (lang, guide)
                for key, fields in variants.items():
                    assert set(theirs[key]) == set(fields), (lang, guide, key)
                    if "steps" in fields:
                        assert len(theirs[key]["steps"]) == len(fields["steps"]), (lang, guide, key)
                    for value in theirs[key].values():
                        assert value and all(str(v).strip() for v in (value if isinstance(value, list) else [value]))

    def test_the_variants_this_concept_asked_for(self):
        en = _texts()["en"]
        assert set(en["clean_filter"]["variants"]) == {"600", "900", "eij", "s"}
        assert set(en["clean_brushes"]["variants"]) == {"600", "900", "eij", "s"}
        assert set(en["clean_contact"]["variants"]) == set(cg.DOCKS)
        assert "s" in en["clean_side_brush"]["variants"]
        assert "s" in en["clean_wheel"]["variants"]

    def test_the_robots_text_is_laid_over_the_general_one(self):
        guides = _guides()
        s9 = cg.robot_context("s955020", False)
        assert guides.title("clean_side_brush", "en", s9) == "Clean the corner brush"
        assert guides.title("clean_side_brush", "en") == "Clean the side brush"
        steps = guides.guide("clean_filter", "en", cg.robot_context("R980020", False))["steps"]
        assert "yellow tab" in steps[2]
        base = guides.guide("clean_filter", "en")
        assert "variants" not in base and base["steps"] != steps
        dock = guides.guide("clean_contact", "en", cg.robot_context("R980020", False, "clean_base"))
        assert "Clean Base" in dock["steps"][2]
        # Caution of the general text where the variant has none.
        assert dock["caution"] == base_caution(guides)

    def test_translated_not_copied(self):
        texts = _texts()
        for lang in cg.LANGUAGES:
            if lang == "en":
                continue
            same = [g for g in cg.GUIDES if texts[lang][g]["why"] == texts["en"][g]["why"]]
            assert not same, (lang, same)

    def test_the_notice_names_where_to_get_a_new_link(self):
        for lang, doc in _texts().items():
            assert "Roomba+" in doc["_page"]["expired_text"], lang


class TestTheDrawings:

    @pytest.mark.parametrize("sku", ["R675020", "R980020", "i755020", "s955020", "m611020", None])
    @pytest.mark.parametrize("dock", cg.DOCKS)
    def test_every_guide_with_a_drawing_finds_its_part(self, sku, dock):
        guides = _guides()
        ctx = cg.robot_context(sku, prime=sku is None, dock=dock)
        drawn = {g for g in cg.GUIDE_SCHEMATA if guides.schema_svgs(g, ctx, "en")}
        missing = set(cg.GUIDE_SCHEMATA) - drawn
        if ctx.series == "braava":
            # A Braava has no bin, brushes, wheels or battery cover on
            # its underside drawing; its own parts are there.
            assert {"replace_pad", "clean_cliff_sensors", "clean_contact"} <= drawn
        else:
            assert missing == {"replace_pad"}, (sku, missing)
        # Every drawing the guide names exists: none silently missing.
        for guide in cg.GUIDE_SCHEMATA:
            for stem, part in cg.schema_names(guide, ctx):
                if part != "pad" or ctx.series == "braava":
                    assert stem in guides._schemata, (guide, stem)

    def test_the_contacts_show_the_robot_and_its_dock(self):
        guides = _guides()
        for dock in cg.DOCKS:
            ctx = cg.robot_context("R980020", False, dock)
            svgs = guides.schema_svgs("clean_contact", ctx, "en")
            assert len(svgs) == 2
            assert "Underside" not in svgs[1] and "#part-contact .hal" in svgs[1]

    def test_each_part_has_a_numbered_marker_and_a_halo(self):
        _texts_, schemata = cg._read_files()
        for stem, svg in schemata.items():
            for part in re.findall(r'<g id="part-([a-z_]+)">', svg):
                assert f'id="m-{part}"' in svg, (stem, part)
                start = svg.index(f'<g id="part-{part}">')
                assert '<g class="hal">' in svg[start:start + 200], (stem, part)

    def test_nothing_is_highlighted_in_the_file_and_the_dark_mode_is_there(self):
        _texts_, schemata = cg._read_files()
        for stem, svg in schemata.items():
            assert ".mk{display:none}" in svg and ".hal{display:none" in svg, stem
            assert "prefers-color-scheme:dark" in svg, stem
            assert "<script" not in svg and "href" not in svg, stem

    def test_the_highlight_shows_the_part_its_halo_and_marker(self):
        svg = cg.highlight("<svg><title>x</title></svg>", "side_brush", "Clean <it>")
        assert "<title>Clean &lt;it&gt;</title>" in svg
        assert "#part-side_brush .hal{display:inline}" in svg
        assert "#m-side_brush{display:inline}" in svg

    def test_in_dark_mode_lines_off_the_fill_turn_pale(self):
        """THE BUG IN THE PREVIEW: the side brush's arms and bristles were
        drawn in the dark outline colour -- invisible on a dark page."""
        svg = cg.highlight("<svg></svg>", "side_brush")
        dark = svg[svg.index("prefers-color-scheme:dark"):]
        assert "#part-side_brush .ln,#part-side_brush .brs{stroke:#FFE7A8}" in dark

    def test_the_side_brush_bristles_carry_the_class(self):
        _texts_, schemata = cg._read_files()
        for stem in ("underside_600_900", "underside_eij", "underside_s"):
            assert 'class="fine brs"' in schemata[stem], stem


class TestWhichGuide:

    @pytest.mark.parametrize("action,part,guide", [
        ("replace", "filter", "replace_filter"),
        ("replace", "main_brush", "replace_main_brush"),
        ("replace", "clean_base_bag", "replace_bag"),
        ("replace", "bag", "replace_bag"),
        ("replace", "pad", "replace_pad"),
        ("replace", "sensor", "clean_cliff_sensors"),
        ("replace", "mop_washing_system", "clean_mop_washing_system"),
        ("clean", "brushes", "clean_brushes"),
        ("clean", "main_brush", "clean_brushes"),
        ("clean", "sensor", "clean_cliff_sensors"),
        ("check", "bin", "clean_bin"),
        ("check", "camera", "clean_camera"),
        ("clean", "dock_washing_system", "clean_dock_washing_system"),
        ("replace", "part_202", None),
        ("other", "filter", None),
    ])
    def test_guide_id(self, action, part, guide):
        assert cg.guide_id(action, part) == guide

    @pytest.mark.parametrize("sku,prime,series,underside,bin_", [
        ("R980020", False, "900", "600_900", "600_900"),
        ("R675020", False, "600", "600_900", "600_900"),
        ("e515020", False, "eij", "eij", "eij"),
        ("i755020", False, "eij", "eij", "eij"),
        ("c975860", False, "eij", "eij", "eij"),
        ("s955020", False, "s", "s", "s"),
        ("m613320", False, "braava", "braava", "eij"),
        (None, False, None, "eij", "eij"),
        ("R980020", True, None, "eij", "eij"),
    ])
    def test_the_robot_context(self, sku, prime, series, underside, bin_):
        ctx = cg.robot_context(sku, prime)
        assert (ctx.series, ctx.underside, ctx.bin) == (series, underside, bin_)
        assert cg.variant_for(sku, prime) == underside

    def test_the_dock_from_the_parts_the_robot_has(self):
        from custom_components.roomba_plus.models import ConnectionType

        def data(*parts, prime=False):
            return SimpleNamespace(
                connection_type=ConnectionType.CLOUD_ONLY if prime else ConnectionType.LOCAL_PUSH,
                roomba_reported_state=lambda: {"sku": "i755020"},
                maintenance=SimpleNamespace(items=[SimpleNamespace(part=p) for p in parts]),
            )

        assert cg.context_for(data("filter")).dock == "home_base"
        assert cg.context_for(data("filter", "clean_base_bag")).dock == "clean_base"
        assert cg.context_for(data("bag", prime=True)).dock == "clean_base"
        assert cg.context_for(data("dock_washing_system", "bag", prime=True)).dock == "wash_dock"
        assert cg.context_for(data()).series == "eij"
        assert cg.context_for(data(prime=True)).series is None
        assert cg.context_for(None) == cg.GENERIC

    @pytest.mark.parametrize("ha,lang", [
        ("de", "de"), ("pt-BR", "pt"), ("en_GB", "en"), ("zh-Hans", "en"), (None, "en"),
    ])
    def test_the_language(self, ha, lang):
        assert cg.language_for(ha) == lang

    def test_irobot_link_falls_back_to_the_replacement_twin_and_only_https(self):
        items = [
            SimpleNamespace(guide_id="replace_filter", guide_url="https://example.com/f"),
            SimpleNamespace(guide_id="replace_bag", guide_url="javascript:alert(1)"),
        ]
        assert cg.irobot_link(items, "clean_filter") == "https://example.com/f"
        assert cg.irobot_link(items, "replace_bag") is None
        assert cg.irobot_link(items, "clean_wheel") is None


class TestTheSignature:

    def test_a_link_checks_and_holds_31_to_37_days(self):
        guides = _guides()
        path = guides.page_path("E1", "clean_filter", "de", _NOW)
        query = dict(p.split("=", 1) for p in path.split("?", 1)[1].split("&"))
        assert path.startswith("/api/roomba_plus/care/E1/clean_filter?lang=de&exp=")
        assert guides.check("E1", "clean_filter", query, _NOW) == "ok"
        assert guides.check("E1", "clean_filter", query, _NOW + timedelta(days=30)) == "ok"
        assert guides.check("E1", "clean_filter", query, _NOW + timedelta(days=38)) == "expired"
        for day in range(7):
            exp = cg.expiry_day(_NOW + timedelta(days=day))
            assert 31 <= exp - cg._epoch_day(_NOW + timedelta(days=day)) <= 37

    def test_a_week_of_recomputes_keeps_the_same_link(self):
        guides = _guides()
        # Weeks count from 1 January 1970, a Thursday.
        week_start = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
        assert cg._epoch_day(week_start) % 7 == 0
        links = {guides.page_path("E1", "clean_filter", "en", week_start + timedelta(hours=h))
                 for h in range(0, 7 * 24, 6)}
        assert len(links) == 1

    @pytest.mark.parametrize("change", [
        {"lang": "en"}, {"exp": "99999"}, {"sig": "AAAAAAAAAAAAAAAAAAAAAA"}, {"exp": "x"},
    ])
    def test_anything_changed_is_refused(self, change):
        guides = _guides()
        path = guides.page_path("E1", "clean_filter", "de", _NOW)
        query = dict(p.split("=", 1) for p in path.split("?", 1)[1].split("&"))
        assert guides.check("E1", "clean_filter", {**query, **change}, _NOW) == "bad"

    def test_another_entry_guide_or_secret_is_refused(self):
        guides = _guides()
        path = guides.page_path("E1", "clean_filter", "de", _NOW)
        query = dict(p.split("=", 1) for p in path.split("?", 1)[1].split("&"))
        assert guides.check("E2", "clean_filter", query, _NOW) == "bad"
        assert guides.check("E1", "clean_bin", query, _NOW) == "bad"
        other = cg.CareGuides(b"t" * 32, {}, {})
        assert other.check("E1", "clean_filter", query, _NOW) == "bad"

    def test_no_link_for_an_unknown_guide(self):
        guides = _guides()
        assert guides.page_path("E1", "nope", "en") is None
        assert guides.schema_path("E1", "clean_camera", "en") is None


class TestThePage:

    def test_the_page_has_the_drawing_why_steps_note_and_link(self):
        page = _guides().page(
            "clean_side_brush", "de", cg.robot_context("i755020", False),
            "https://example.com/g?a=1&b=2",
        )
        assert page.startswith('<!doctype html><html lang="de">')
        assert "<h1>Seitenbürste reinigen</h1>" in page
        assert "<svg" in page and "#part-side_brush .hal{display:inline}" in page
        assert page.count("<li>") == 4
        assert 'href="https://example.com/g?a=1&amp;b=2"' in page
        assert "<script" not in page

    def test_no_drawing_no_link_where_there_is_none(self):
        page = _guides().page("clean_camera", "en")
        assert "<svg" not in page and 'class="more"' not in page

    def test_text_is_escaped(self):
        texts = {"en": {"_page": {"why": "<b>"}, "clean_filter": {
            "title": "<script>x</script>", "why": "a&b", "steps": ["<i>"], "caution": "\""}}}
        page = cg.CareGuides(b"s" * 32, texts, {}).page("clean_filter", "en")
        assert "<script>x" not in page and "&lt;script&gt;" in page
        assert "<i>" not in page and "a&amp;b" in page

    def test_the_form_markdown(self):
        text = _guides().markdown("clean_wheel", "en", "![x](/p)")
        assert text.startswith("![x](/p)\n\n**What it does**")
        assert "\n1. " in text and "\n3. " in text


def _request(hass, query):
    return SimpleNamespace(app={"hass": hass}, query=query)


def _query(path: str) -> dict[str, str]:
    return dict(p.split("=", 1) for p in path.split("?", 1)[1].split("&"))


class TestTheViews:

    async def test_setup_keeps_one_secret_and_registers_the_views(self, hass, hass_storage):
        hass.http = MagicMock()
        guides = await cg.async_setup_care_guides(hass)
        assert guides is not None
        assert await cg.async_setup_care_guides(hass) is guides
        assert hass.http.register_view.call_count == 2
        secret = hass_storage[cg._STORE_KEY]["data"]["secret"]
        assert len(secret) == 64
        hass.data.pop(cg._DATA_KEY)
        again = await cg.async_setup_care_guides(hass)
        assert again._secret == guides._secret, "the secret survives a restart"

    async def test_a_broken_store_costs_the_links_only(self, hass):
        from unittest.mock import patch

        with patch.object(cg, "_read_files", side_effect=OSError("disk")):
            assert await cg.async_setup_care_guides(hass) is None
        assert cg.get_care_guides(hass) is None
        assert cg.guide_link(hass, "E1", "clean_filter") is None

    async def test_the_page_view(self, hass):
        guides = _guides()
        hass.data[cg._DATA_KEY] = guides
        path = guides.page_path("E1", "clean_filter", "fr")
        view = cg.CareGuidePageView()
        assert view.requires_auth is False
        ok = await view.get(_request(hass, _query(path)), "E1", "clean_filter")
        assert ok.status == 200 and ok.content_type == "text/html"
        assert "Nettoyer le filtre" in ok.text
        assert ok.headers["Referrer-Policy"] == "no-referrer"
        assert "default-src 'none'" in ok.headers["Content-Security-Policy"]
        bad = await view.get(_request(hass, {**_query(path), "sig": "x"}), "E1", "clean_filter")
        assert bad.status == 404 and "Nettoyer le filtre" not in bad.text
        assert guides.text("fr")["_page"]["unknown_title"] in bad.text

    async def test_the_page_says_when_like_the_dialog(self, hass):
        """4.5.0b2: the page lacked the dialog's "When". It comes from the
        robot's entry when the page is opened, in the link's language."""
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.roomba_plus.const import DOMAIN
        from custom_components.roomba_plus.maintenance_model import MaintenanceItem
        from custom_components.roomba_plus.models import ConnectionType

        guides = _guides()
        hass.data[cg._DATA_KEY] = guides
        entry = MockConfigEntry(domain=DOMAIN, title="Robo")
        entry.add_to_hass(hass)
        entry.runtime_data = SimpleNamespace(
            connection_type=ConnectionType.LOCAL_PUSH,
            roomba_reported_state=lambda: {"sku": "R980020"},
            maintenance=SimpleNamespace(items=[
                MaintenanceItem("replace.filter", "replace", "filter", guide_id="clean_filter",
                                remaining=99.0, unit="hours"),
                MaintenanceItem("clean.filter", "clean", "filter", guide_id="clean_filter",
                                interval=7.0, interval_unit="days", interval_source="calendar",
                                remaining=3.0, unit="days"),
            ]),
        )
        wording = {"interval_line": "Interval {value} {unit}, {source}",
                   "left": "{value} {unit} left", "unit_days": "days",
                   "source_calendar": "on the care calendar"}
        path = guides.page_path(entry.entry_id, "clean_filter", "en")
        with patch.object(cg, "async_wording", AsyncMock(return_value=wording)) as words:
            page = await cg.CareGuidePageView().get(
                _request(hass, _query(path)), entry.entry_id, "clean_filter",
            )
        words.assert_awaited_once_with(hass, "en")
        assert page.status == 200
        when = f"<h2>{guides.text('en')['_page']['when']}</h2>"
        assert when in page.text, "the care task's entry, not the replacement's"
        assert "3 days left" in page.text and "99 hours" not in page.text
        assert page.text.index(when) < page.text.index(f"<h2>{guides.text('en')['_page']['how']}</h2>")

        gone = guides.page_path("gone", "clean_filter", "en")
        with patch.object(cg, "async_wording", AsyncMock(return_value=wording)):
            page = await cg.CareGuidePageView().get(_request(hass, _query(gone)), "gone", "clean_filter")
        assert page.status == 200 and when not in page.text, "no entry, no When"

    async def test_an_expired_link_says_so_in_its_language(self, hass):
        guides = _guides()
        hass.data[cg._DATA_KEY] = guides
        path = guides.page_path("E1", "clean_filter", "nl", _NOW - timedelta(days=60))
        page = await cg.CareGuidePageView().get(_request(hass, _query(path)), "E1", "clean_filter")
        assert page.status == 410
        assert guides.text("nl")["_page"]["expired_title"] in page.text

    async def test_the_schema_view(self, hass):
        guides = _guides()
        hass.data[cg._DATA_KEY] = guides
        view = cg.CareGuideSchemaView()
        path = guides.schema_path("E1", "replace_bag", "en")
        svg = await view.get(_request(hass, _query(path)), "E1", "replace_bag")
        assert svg.status == 200 and svg.content_type == "image/svg+xml"
        assert "#part-bag .hal{display:inline}" in svg.text
        refused = await view.get(_request(hass, {**_query(path), "exp": "1"}), "E1", "replace_bag")
        assert refused.status == 404

    async def test_the_robots_drawing_and_irobots_link_from_its_entry(self, hass):
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.roomba_plus.const import DOMAIN
        from custom_components.roomba_plus.models import ConnectionType

        entry = MockConfigEntry(domain=DOMAIN, title="Robo")
        entry.add_to_hass(hass)
        entry.runtime_data = SimpleNamespace(
            connection_type=ConnectionType.LOCAL_PUSH,
            roomba_reported_state=lambda: {"sku": "R980020"},
            maintenance=SimpleNamespace(items=[SimpleNamespace(
                guide_id="replace_main_brush", guide_url="https://example.com/b",
            )]),
        )
        ctx, link = cg._entry_context(hass, entry.entry_id, "clean_brushes")
        assert (ctx.series, ctx.underside, link) == ("900", "600_900", "https://example.com/b")
        assert cg._entry_context(hass, "gone", "clean_brushes") == (cg.GENERIC, None)
        entry.runtime_data.connection_type = ConnectionType.CLOUD_ONLY
        ctx, link = cg._entry_context(hass, entry.entry_id, "clean_wheel")
        assert (ctx.series, link) == (None, None)


def test_the_title_for_a_notification():
    hass = SimpleNamespace(data={cg._DATA_KEY: _guides()}, config=SimpleNamespace(language="de"))
    assert cg.guide_title(hass, "clean_filter") == "Filter reinigen"
    assert cg.guide_title(hass, None) is None
    assert cg.guide_title(SimpleNamespace(data={}), "clean_filter") is None


# ── The guides on GitHub: docs/care/ (4.5.0) ────────────────────────────────

def _care_docs():
    import importlib.util

    path = Path(__file__).parent.parent / "scripts" / "build_care_docs.py"
    spec = importlib.util.spec_from_file_location("build_care_docs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheGuidesOnGitHub:
    """docs/care/ is made from the integration's own texts and drawings by
    scripts/build_care_docs.py. Changed a text and forgot the script: this
    fails."""

    def test_docs_care_is_what_the_script_writes(self):
        module = _care_docs()
        files = module.build()
        docs = module.DOCS
        on_disk = {str(p.relative_to(docs)) for p in docs.rglob("*") if p.is_file()}
        assert on_disk == set(files), "run: python scripts/build_care_docs.py"
        stale = [p for p, text in files.items() if (docs / p).read_text(encoding="utf-8") != text]
        assert stale == [], "run: python scripts/build_care_docs.py"

    def test_every_language_and_guide_with_its_drawings(self):
        files = _care_docs().build()
        for lang in cg.LANGUAGES:
            assert f"{lang}/README.md" in files
            for guide in cg.GUIDES:
                page = files[f"{lang}/{guide}.md"]
                for image in re.findall(r"\]\(\.\./(img/[^)]+)\)", page):
                    assert image in files, (lang, guide, image)

    def test_a_page_names_only_the_robots_it_is_for(self):
        files = _care_docs().build()
        filters = files["en/clean_filter.md"]
        assert "## Roomba 600 and 700 series\n" in filters and "## Roomba s series\n" in filters
        assert "Braava" not in filters, "a Braava has no filter"
        bag = files["en/replace_bag.md"]
        assert "## " not in bag and "600" not in bag, "the same for every Clean Base robot"
        contacts = files["de/clean_contact.md"]
        assert "## Clean Base: Roomba e, i und j, Combo j · Prime-Roboter und andere Modelle" in contacts


def test_an_expired_link_points_to_the_guides_on_github():
    guides = _guides()
    page = guides.notice("pl", "expired")
    assert 'href="https://github.com/johnnyh1975/ha_roomba_plus/blob/main/docs/care/pl/README.md"' in page
    assert guides.text("pl")["_page"]["docs"] in page
