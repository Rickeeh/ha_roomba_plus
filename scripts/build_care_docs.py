"""Write the care guides as Markdown pages under docs/care/ (4.5.0).

    python scripts/build_care_docs.py           write docs/care/
    python scripts/build_care_docs.py --check   exit 1 if docs/care/ is stale

The pages are made from the same texts and drawings the integration
shows (custom_components/roomba_plus/care/), through its own CareGuides
class, so they cannot say anything Home Assistant does not. Run it with
the Python that has Home Assistant installed. A test keeps docs/care/
equal to what this writes (tests/test_care_guides.py).

One page per guide and language. Where robots differ -- the 600 empties
its bin another way than an s, the contacts differ by dock -- the page
has a section per group of robots that get the same guide; a guide that
is the same for every robot has none.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from custom_components.roomba_plus import care_guides as cg  # noqa: E402

DOCS = ROOT / "docs" / "care"
IMAGES = "img"

#: Which docks each kind of robot comes with. A 600 has no Clean Base,
#: so its section never says "with Clean Base".
SERIES_DOCKS: dict[str | None, tuple[str, ...]] = {
    "600": ("home_base",),
    "900": ("home_base",),
    "eij": ("home_base", "clean_base", "wash_dock"),
    "s": ("home_base", "clean_base"),
    "braava": ("home_base",),
    None: ("home_base", "clean_base", "wash_dock"),
}
SERIES_ORDER: tuple[str | None, ...] = ("600", "900", "eij", "s", "braava", None)

_VACUUMS = frozenset({"600", "900", "eij", "s", None})
_WASH = frozenset({"eij", None})
#: Which robots and docks a guide is for. The integration only offers a
#: guide for a part the robot has; a page lists only those robots, so a
#: 600 is not told how to change a Clean Base bag. Docks: None = all the
#: robot's own.
GUIDE_SCOPE: dict[str, tuple[frozenset[str | None], tuple[str, ...] | None]] = {
    "clean_filter": (_VACUUMS, None),
    "replace_filter": (_VACUUMS, None),
    "clean_bin": (_VACUUMS, None),
    "clean_brushes": (_VACUUMS, None),
    "replace_main_brush": (_VACUUMS, None),
    "clean_side_brush": (_VACUUMS, None),
    "replace_side_brush": (_VACUUMS, None),
    "clean_wheel": (_VACUUMS, None),
    "clean_cliff_sensors": (frozenset(SERIES_ORDER), None),
    "clean_contact": (frozenset(SERIES_ORDER), None),
    "replace_battery": (frozenset(SERIES_ORDER), None),
    # Braava jet and the Combo robots.
    "replace_pad": (frozenset({"eij", "braava", None}), None),
    "replace_bag": (frozenset({"eij", "s", None}), ("clean_base",)),
    "clean_wash_dock": (_WASH, ("wash_dock",)),
    "clean_dock_washing_system": (_WASH, ("wash_dock",)),
    "clean_mop_washing_system": (_WASH, ("wash_dock",)),
    "replace_roller": (_WASH, ("wash_dock",)),
    "replace_detergent": (_WASH, ("wash_dock",)),
    # A camera or front sensor windows: j, s and the Prime robots.
    "clean_camera": (frozenset({"eij", "s", None}), None),
}

#: The robots as `robot_context()` builds them, by series.
_SKU = {"600": "R690000", "900": "R980020", "eij": "i755020", "s": "s955020", "braava": "m613840"}

LANGUAGE_NAMES = {
    "en": "English", "de": "Deutsch", "fr": "Français", "es": "Español",
    "it": "Italiano", "nl": "Nederlands", "pl": "Polski", "pt": "Português",
}

#: The few words the pages need besides the guides' own texts.
LABELS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Care guides",
        "intro": "Written and drawn for Roomba+. In Home Assistant, Settings → Devices & services → "
                 "Roomba+ → Configure → Maintenance → Care guides shows the one for your robot, "
                 "with when it is due.",
        "all": "All care guides",
        "languages": "Other languages",
        "600": "Roomba 600 and 700 series", "900": "Roomba 800 and 900 series",
        "eij": "Roomba e, i and j series, Combo j", "s": "Roomba s series",
        "braava": "Braava jet", "none": "Prime robots and other models",
        "home_base": "Home Base", "clean_base": "Clean Base", "wash_dock": "washing station",
    },
    "de": {
        "title": "Pflegeanleitungen",
        "intro": "Für Roomba+ geschrieben und gezeichnet. In Home Assistant zeigt Einstellungen → "
                 "Geräte & Dienste → Roomba+ → Konfigurieren → Wartung → Pflegeanleitungen die für "
                 "deinen Roboter, mit dem nächsten Termin.",
        "all": "Alle Pflegeanleitungen",
        "languages": "Andere Sprachen",
        "600": "Roomba 600er und 700er", "900": "Roomba 800er und 900er",
        "eij": "Roomba e, i und j, Combo j", "s": "Roomba s",
        "braava": "Braava jet", "none": "Prime-Roboter und andere Modelle",
        "home_base": "Home Base", "clean_base": "Clean Base", "wash_dock": "Wasch-Dock",
    },
    "fr": {
        "title": "Guides d'entretien",
        "intro": "Écrits et dessinés pour Roomba+. Dans Home Assistant, Paramètres → Appareils et "
                 "services → Roomba+ → Configurer → Entretien → Guides d'entretien affiche celui de "
                 "votre robot, avec la prochaine échéance.",
        "all": "Tous les guides d'entretien",
        "languages": "Autres langues",
        "600": "Roomba séries 600 et 700", "900": "Roomba séries 800 et 900",
        "eij": "Roomba séries e, i et j, Combo j", "s": "Roomba série s",
        "braava": "Braava jet", "none": "Robots Prime et autres modèles",
        "home_base": "Home Base", "clean_base": "Clean Base", "wash_dock": "station de lavage",
    },
    "es": {
        "title": "Guías de cuidado",
        "intro": "Escritas y dibujadas para Roomba+. En Home Assistant, Ajustes → Dispositivos y "
                 "servicios → Roomba+ → Configurar → Mantenimiento → Guías de cuidado muestra la de "
                 "tu robot, con su próxima fecha.",
        "all": "Todas las guías de cuidado",
        "languages": "Otros idiomas",
        "600": "Roomba series 600 y 700", "900": "Roomba series 800 y 900",
        "eij": "Roomba series e, i y j, Combo j", "s": "Roomba serie s",
        "braava": "Braava jet", "none": "Robots Prime y otros modelos",
        "home_base": "Home Base", "clean_base": "Clean Base", "wash_dock": "base de lavado",
    },
    "it": {
        "title": "Guide di cura",
        "intro": "Scritte e disegnate per Roomba+. In Home Assistant, Impostazioni → Dispositivi e "
                 "servizi → Roomba+ → Configura → Manutenzione → Guide di cura mostra quella del tuo "
                 "robot, con la prossima scadenza.",
        "all": "Tutte le guide di cura",
        "languages": "Altre lingue",
        "600": "Roomba serie 600 e 700", "900": "Roomba serie 800 e 900",
        "eij": "Roomba serie e, i e j, Combo j", "s": "Roomba serie s",
        "braava": "Braava jet", "none": "Robot Prime e altri modelli",
        "home_base": "Home Base", "clean_base": "Clean Base", "wash_dock": "base di lavaggio",
    },
    "nl": {
        "title": "Verzorgingshandleidingen",
        "intro": "Geschreven en getekend voor Roomba+. In Home Assistant toont Instellingen → "
                 "Apparaten & diensten → Roomba+ → Configureren → Onderhoud → "
                 "Verzorgingshandleidingen die voor jouw robot, met de volgende keer.",
        "all": "Alle verzorgingshandleidingen",
        "languages": "Andere talen",
        "600": "Roomba 600- en 700-serie", "900": "Roomba 800- en 900-serie",
        "eij": "Roomba e-, i- en j-serie, Combo j", "s": "Roomba s-serie",
        "braava": "Braava jet", "none": "Prime-robots en andere modellen",
        "home_base": "Home Base", "clean_base": "Clean Base", "wash_dock": "wasstation",
    },
    "pl": {
        "title": "Instrukcje pielęgnacji",
        "intro": "Napisane i narysowane dla Roomba+. W Home Assistant Ustawienia → Urządzenia oraz "
                 "usługi → Roomba+ → Konfiguruj → Konserwacja → Instrukcje pielęgnacji pokazuje "
                 "instrukcję dla twojego robota wraz z terminem.",
        "all": "Wszystkie instrukcje pielęgnacji",
        "languages": "Inne języki",
        "600": "Roomba serii 600 i 700", "900": "Roomba serii 800 i 900",
        "eij": "Roomba serii e, i oraz j, Combo j", "s": "Roomba serii s",
        "braava": "Braava jet", "none": "Roboty Prime i inne modele",
        "home_base": "Home Base", "clean_base": "Clean Base", "wash_dock": "stacja myjąca",
    },
    "pt": {
        "title": "Guias de cuidados",
        "intro": "Escritos e desenhados para o Roomba+. No Home Assistant, Definições → Dispositivos "
                 "e serviços → Roomba+ → Configurar → Manutenção → Guias de cuidados mostra o do seu "
                 "robô, com a próxima data.",
        "all": "Todos os guias de cuidados",
        "languages": "Outros idiomas",
        "600": "Roomba séries 600 e 700", "900": "Roomba séries 800 e 900",
        "eij": "Roomba séries e, i e j, Combo j", "s": "Roomba série s",
        "braava": "Braava jet", "none": "Robôs Prime e outros modelos",
        "home_base": "Home Base", "clean_base": "Clean Base", "wash_dock": "estação de lavagem",
    },
}

GENERATED = (
    "<!-- Generated by scripts/build_care_docs.py from "
    "custom_components/roomba_plus/care/. Do not edit: change the texts "
    "or drawings there and run the script. -->"
)


def _context(series: str | None, dock: str) -> cg.RobotContext:
    return cg.robot_context(_SKU.get(series or ""), series is None, dock)


def _image(svg: str, stem: str, part: str, files: dict[str, str]) -> str:
    """The drawing's file name, language-free: the alt text carries the
    language, the drawing's own <title> stays."""
    name = f"{stem}--{part}.svg"
    files[f"{IMAGES}/{name}"] = cg.highlight(svg, part)
    return name


def _block(guides: cg.CareGuides, guide: str, lang: str, ctx: cg.RobotContext,
           schemata: dict[str, str], files: dict[str, str]) -> str:
    page = guides.text(lang).get("_page") or {}
    g = guides.guide(guide, lang, ctx)
    title = guides.title(guide, lang, ctx)
    pictures = [
        f"![{title}](../{IMAGES}/{_image(schemata[stem], stem, part, files)})"
        for stem, part in cg.schema_names(guide, ctx)
        if stem in schemata and f'id="part-{part}"' in schemata[stem]
    ]
    steps = "\n".join(f"{n}. {s}" for n, s in enumerate(g.get("steps") or [], 1))
    parts = [
        "\n\n".join(pictures),
        f"**{page.get('why', '')}**\n\n{g.get('why', '')}",
        f"**{page.get('how', '')}**\n\n{steps}",
        f"> **{page.get('note', '')}** {g.get('caution', '')}",
    ]
    return "\n\n".join(p for p in parts if p)


def _combos(guide: str) -> list[tuple[str | None, str]]:
    """The robots and docks a guide's page covers."""
    series_in, docks_in = GUIDE_SCOPE[guide]
    return [
        (series, dock)
        for series in SERIES_ORDER if series in series_in
        for dock in SERIES_DOCKS[series] if docks_in is None or dock in docks_in
    ]


def _label(lang: str, combos: list[tuple[str | None, str]], scope: list[tuple[str | None, str]]) -> str:
    """The robots a section is for. A dock is named only where the page
    tells docks apart, and then once for all the robots that share it."""
    words = LABELS[lang]
    names = [words[s or "none"] for s in SERIES_ORDER if any(c[0] == s for c in combos)]
    docks = [d for d in dict.fromkeys(d for _, d in combos)]
    scope_docks = {series: [d for s, d in scope if s == series] for series in SERIES_ORDER}
    whole = all(
        [d for s, d in combos if s == series] == scope_docks[series]
        for series in SERIES_ORDER if any(c[0] == series for c in combos)
    )
    label = " · ".join(names)
    if not whole:
        label = ", ".join(words[d] for d in docks) + ": " + label
    return label


def guide_page(guides: cg.CareGuides, guide: str, lang: str, schemata: dict[str, str],
               files: dict[str, str]) -> str:
    scope = _combos(guide)
    groups: dict[str, list[tuple[str | None, str]]] = {}
    for series, dock in scope:
        text = _block(guides, guide, lang, _context(series, dock), schemata, files)
        groups.setdefault(text, []).append((series, dock))
    words = LABELS[lang]
    title = guides.title(guide, lang)
    head = [GENERATED, f"# {title}", f"[{words['all']}](README.md)"]
    if len(groups) == 1:
        body = [next(iter(groups))]
    else:
        body = [f"## {_label(lang, combos, scope)}\n\n{text}" for text, combos in groups.items()]
    return "\n\n".join(head + body) + "\n"


def index_page(guides: cg.CareGuides, lang: str) -> str:
    words = LABELS[lang]
    others = " · ".join(
        f"[{LANGUAGE_NAMES[other]}](../{other}/README.md)"
        for other in cg.LANGUAGES if other != lang
    )
    rows = "\n".join(f"- [{guides.title(g, lang)}]({g}.md)" for g in cg.GUIDES)
    return (
        f"{GENERATED}\n\n# {words['title']}\n\n{words['intro']}\n\n{rows}\n\n"
        f"{words['languages']}: {others}\n"
    )


def root_page() -> str:
    rows = "\n".join(
        f"- [{LANGUAGE_NAMES[lang]} – {LABELS[lang]['title']}]({lang}/README.md)"
        for lang in cg.LANGUAGES
    )
    return f"{GENERATED}\n\n# Care guides\n\n{rows}\n"


def build() -> dict[str, str]:
    """Every file of docs/care/, by its path there."""
    texts, schemata = cg._read_files()
    guides = cg.CareGuides(b"\0" * 32, texts, schemata)
    files: dict[str, str] = {"README.md": root_page()}
    for lang in cg.LANGUAGES:
        files[f"{lang}/README.md"] = index_page(guides, lang)
        for guide in cg.GUIDES:
            files[f"{lang}/{guide}.md"] = guide_page(guides, guide, lang, schemata, files)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only report a stale docs/care/")
    args = parser.parse_args()
    files = build()
    on_disk = {str(p.relative_to(DOCS)) for p in DOCS.rglob("*") if p.is_file()} if DOCS.is_dir() else set()
    stale = sorted(
        path for path, content in files.items()
        if not (DOCS / path).is_file() or (DOCS / path).read_text(encoding="utf-8") != content
    )
    extra = sorted(on_disk - set(files))
    if args.check:
        for path in stale:
            print(f"stale: docs/care/{path}")
        for path in extra:
            print(f"not generated: docs/care/{path}")
        if stale or extra:
            print("Run: python scripts/build_care_docs.py")
            return 1
        print(f"OK: docs/care/ matches the care guides ({len(files)} files).")
        return 0
    for path in extra:
        (DOCS / path).unlink()
    for path, content in files.items():
        target = DOCS / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"Wrote {len(files)} files to docs/care/ ({len(stale)} changed, {len(extra)} removed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
