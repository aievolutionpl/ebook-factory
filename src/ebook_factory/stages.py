"""Deterministic demo stage handlers.

Each handler has signature (project, project_dir) -> StageResult and produces
real files on disk. No paid/external LLM API is used here; this adapter
proves the pipeline end to end. A future Hermes/LLM adapter can implement the
same handler signature and be swapped in via PipelineRunner(stage_handlers=...).
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path

from .artifacts import (
    build_cover_png,
    build_cover_svg,
    build_delivery_zip,
    build_epub,
    build_manifest,
    build_pdf,
)
from .models import MODE_CONFIG, Project
from .pdfcheck import check_pdf
from .pipeline import StageResult
from .workspace import compute_metrics

CHAPTER_TEMPLATES = [
    "Wprowadzenie do tematu",
    "Dlaczego to ma znaczenie",
    "Pierwsze kroki",
    "Najczestsze bledy",
    "Narzedzia i zasoby",
    "Studium przypadku",
    "Zaawansowane techniki",
    "Mierzenie efektow",
    "Skalowanie dzialan",
    "Utrzymanie wynikow",
    "Checklisty i szablony",
    "Plan wdrozenia",
    "Pytania i odpowiedzi",
    "Podsumowanie i nastepne kroki",
]

_SENTENCE_TEMPLATES = [
    "W tym rozdziale pokazujemy, jak {topic} wplywa na codzienna prace {audience}.",
    "Celem jest przedstawienie prostego planu dzialania mozliwego do wdrozenia bez specjalistycznej wiedzy.",
    "Ton tego materialu jest {tone}, dzieki czemu latwiej przelozyc teorie na konkretne kroki.",
    "Marka {brand} przygotowala ten material jako demonstracje pelnego procesu produkcji ebooka.",
    "Kazdy krok opisany ponizej mozna dostosowac do wlasnej sytuacji i dostepnych zasobow.",
    "Warto zaczac od malych eksperymentow, zanim podejmie sie decyzje o pelnym wdrozeniu.",
    "Ponizsze wskazowki maja charakter demonstracyjny i pokazuja strukture, a nie gotowa tresc ekspercka.",
    "Zwroc uwage na to, jak poszczegolne elementy lacza sie w spojna calosc.",
    "Kolejny akapit rozwija te mysl i pokazuje przykladowe zastosowanie w praktyce.",
    "Notatki z researchu oraz zrodla demonstracyjne znajduja sie w osobnym pliku paczki.",
    "Regularne przegladanie postepow pomaga utrzymac tempo pracy nad tematem {topic}.",
    "Podsumowujac ten fragment, kluczowe jest konsekwentne stosowanie prostych zasad.",
]

_TODO_MARKERS = ("TODO", "LOREM IPSUM", "FIXME")


def _find_typst_binary() -> str | None:
    candidate = Path.home() / ".local" / "bin" / "typst"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("typst")
    return found


def _generate_chapter_paragraphs(
    topic: str, audience: str, tone: str, brand: str, chapter_title: str, target_words: int
) -> list[str]:
    sentences = [
        template.format(
            topic=topic,
            audience=audience or "czytelnikow",
            tone=tone or "rzeczowy",
            brand=brand or "Ebook Factory",
        )
        for template in _SENTENCE_TEMPLATES
    ]
    offset = sum(ord(c) for c in chapter_title) % len(sentences)
    words_count = 0
    paragraphs: list[str] = []
    current: list[str] = []
    i = 0
    while words_count < target_words:
        sentence = sentences[(offset + i) % len(sentences)]
        current.append(sentence)
        words_count += len(sentence.split())
        i += 1
        if len(current) >= 4:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _chapter_markdown(title: str, paragraphs: list[str]) -> str:
    body = "\n\n".join(paragraphs)
    return f"# {title}\n\n{body}\n"


def _parse_chapter_markdown(path: Path) -> tuple[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else path.stem
    rest = "\n".join(lines[1:]).strip()
    paragraphs = [p.strip() for p in rest.split("\n\n") if p.strip()]
    return title, paragraphs


def strategy_stage(project: Project, project_dir: Path) -> StageResult:
    config = MODE_CONFIG[project.mode]
    content = (
        f"# Strategia — {project.title}\n\n"
        f"**Temat:** {project.topic}\n"
        f"**Tryb:** {config.label} ({config.page_range[0]}-{config.page_range[1]} stron)\n"
        f"**Jezyk:** {project.language}\n"
        f"**Odbiorca:** {project.audience or 'nieokreslony — do uzupelnienia przed sprzedaza'}\n"
        f"**Marka:** {project.brand or 'Ebook Factory Demo'}\n"
        f"**Ton:** {project.tone or 'rzeczowy'}\n\n"
        "## Obietnica\n"
        f"Ten ebook pokazuje odbiorcy konkretna sciezke do wykorzystania tematu "
        f"„{project.topic}” w praktyce.\n\n"
        "## Pozycjonowanie\n"
        "Material demonstracyjny wygenerowany przez pipeline Ebook Factory — "
        "struktura i proces sa realne, tresc wymaga redakcji eksperckiej przed sprzedaza.\n"
    )
    if project.source_materials:
        content += (
            "\n## Materialy zrodlowe\n"
            "Strategia uwzglednia ponizsze materialy dostarczone przez uzytkownika:\n\n"
            f"{project.source_materials}\n"
        )
    path = project_dir / "outline" / "strategy.md"
    path.write_text(content, encoding="utf-8")
    return StageResult(True, "strategy captured", ["outline/strategy.md"])


def research_stage(project: Project, project_dir: Path) -> StageResult:
    lines = [
        "# Notatki z researchu (DEMO)",
        "",
        "> Ten plik zawiera przykladowe, automatycznie wygenerowane placeholdery zrodel. "
        "W produkcji zastap je prawdziwym researchem i linkami.",
        "",
    ]
    for i in range(1, 6):
        lines.append(
            f"{i}. [DEMO ZRODLO {i}] Materialy o „{project.topic}” — zastap prawdziwym "
            "linkiem, autorem i data publikacji przed uzyciem komercyjnym."
        )
    if project.source_materials:
        lines.append("")
        lines.append("## Materialy zrodlowe dostarczone przez uzytkownika")
        lines.append("")
        lines.append(
            "Research uwzglednia ponizsze materialy jako punkt wyjscia do dalszej weryfikacji:"
        )
        lines.append("")
        lines.append(project.source_materials)
    path = project_dir / "research" / "notes.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return StageResult(True, "research notes captured", ["research/notes.md"])


def resolve_chapter_titles(project: Project) -> tuple[list[str], str]:
    """Pick the chapter structure for a project.

    A custom structure supplied by the operator always wins and is used
    verbatim, including its length. Otherwise the mode preset decides how many
    template chapters to use, repeating the template list when a mode asks for
    more chapters than there are templates.
    """
    custom = [title for title in (project.chapter_titles or []) if title.strip()]
    if custom:
        return custom, "custom"
    config = MODE_CONFIG[project.mode]
    titles: list[str] = []
    for index in range(config.chapter_count):
        base = CHAPTER_TEMPLATES[index % len(CHAPTER_TEMPLATES)]
        cycle = index // len(CHAPTER_TEMPLATES)
        titles.append(base if cycle == 0 else f"{base} ({cycle + 1})")
    return titles, "preset"


def outline_stage(project: Project, project_dir: Path) -> StageResult:
    config = MODE_CONFIG[project.mode]
    titles, source = resolve_chapter_titles(project)
    chapters = [
        {"title": title, "goal": f"Poprowadzic czytelnika przez etap: {title.lower()}"}
        for title in titles
    ]
    outline = {
        "mode": project.mode,
        "topic": project.topic,
        "structure_source": source,
        "words_per_chapter": config.words_per_chapter,
        "chapters": chapters,
    }
    path = project_dir / "outline" / "outline.json"
    path.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
    return StageResult(
        True,
        f"{len(chapters)} chapters planned ({source})",
        ["outline/outline.json"],
    )


def draft_stage(project: Project, project_dir: Path) -> StageResult:
    config = MODE_CONFIG[project.mode]
    outline = json.loads((project_dir / "outline" / "outline.json").read_text(encoding="utf-8"))
    artifact_paths = []
    for index, chapter in enumerate(outline["chapters"], start=1):
        paragraphs = _generate_chapter_paragraphs(
            topic=project.topic,
            audience=project.audience,
            tone=project.tone,
            brand=project.brand,
            chapter_title=chapter["title"],
            target_words=config.words_per_chapter,
        )
        markdown = _chapter_markdown(chapter["title"], paragraphs)
        chapter_path = project_dir / "chapters" / f"chapter-{index:02d}.md"
        chapter_path.write_text(markdown, encoding="utf-8")
        artifact_paths.append(f"chapters/chapter-{index:02d}.md")
    return StageResult(True, f"{len(artifact_paths)} chapters drafted", artifact_paths)


def edit_stage(project: Project, project_dir: Path) -> StageResult:
    chapter_paths = sorted((project_dir / "chapters").glob("chapter-*.md"))
    manuscript_parts = [
        f"# {project.title}",
        "",
        "> Manuskrypt demonstracyjny wygenerowany przez pipeline Ebook Factory. "
        "Tresc pokazuje strukture i proces produkcji; wymaga redakcji eksperckiej "
        "przed sprzedaza.",
        "",
    ]
    for chapter_path in chapter_paths:
        text = chapter_path.read_text(encoding="utf-8")
        cleaned_lines = [line.rstrip() for line in text.splitlines()]
        while cleaned_lines and cleaned_lines[-1] == "":
            cleaned_lines.pop()
        cleaned = "\n".join(cleaned_lines) + "\n"
        for marker in _TODO_MARKERS:
            cleaned = cleaned.replace(marker, "")
        chapter_path.write_text(cleaned, encoding="utf-8")
        manuscript_parts.append(cleaned)
    manuscript_path = project_dir / "builds" / "manuscript.md"
    manuscript_path.write_text("\n".join(manuscript_parts), encoding="utf-8")
    artifact_paths = [f"chapters/{p.name}" for p in chapter_paths] + ["builds/manuscript.md"]
    return StageResult(True, "manuscript edited", artifact_paths)


def fact_check_stage(project: Project, project_dir: Path) -> StageResult:
    chapter_paths = sorted((project_dir / "chapters").glob("chapter-*.md"))
    claim_pattern = re.compile(r"[^.\n]*\d[^.\n]*\.")
    claims: list[str] = []
    for chapter_path in chapter_paths:
        text = chapter_path.read_text(encoding="utf-8")
        claims.extend(m.strip() for m in claim_pattern.findall(text))

    lines = ["# Raport fact-check (DEMO)", ""]
    if claims:
        lines.append(
            "Nastepujace zdania zawieraja liczby i wymagaja weryfikacji zrodlowej "
            "przed publikacja:"
        )
        lines.append("")
        for claim in claims:
            lines.append(f"- {claim} — zrodlo: DO WERYFIKACJI (demo)")
    else:
        lines.append("Brak twierdzen liczbowych wymagajacych weryfikacji w tresci demo.")
    path = project_dir / "qa" / "fact-check.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return StageResult(True, f"{len(claims)} claims logged", ["qa/fact-check.md"])


def design_stage(project: Project, project_dir: Path) -> StageResult:
    svg = build_cover_svg(
        title=project.title, subtitle=project.topic, brand=project.brand, mode=project.mode
    )
    svg_path = project_dir / "images" / "cover.svg"
    svg_path.write_text(svg, encoding="utf-8")
    png_path = project_dir / "images" / "cover.png"
    build_cover_png(
        png_path, title=project.title, subtitle=project.topic, brand=project.brand, mode=project.mode
    )
    return StageResult(True, "cover generated", ["images/cover.svg", "images/cover.png"])


def _front_matter_sections(project: Project, chapter_titles: list[str]) -> list[tuple[str, str]]:
    """Title page, table of contents and colophon, shared by the PDF and EPUB.

    Both builders take the same ``(title, body_html)`` chapter list, so front
    and back matter are expressed as ordinary sections rather than being
    duplicated in two engine-specific templates.
    """
    config = MODE_CONFIG[project.mode]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title_page = "".join(
        f"<p>{html_escape(line)}</p>"
        for line in (
            project.title,
            project.topic,
            f"Autor / marka: {project.brand or 'Ebook Factory'}",
            f"Format: {config.label}",
            f"Jezyk: {project.language}",
            f"Data zlozenia: {today}",
        )
    )
    toc = "".join(
        f"<p>{index}. {html_escape(title)}</p>"
        for index, title in enumerate(chapter_titles, start=1)
    ) or "<p>Brak rozdzialow.</p>"
    colophon = "".join(
        f"<p>{html_escape(line)}</p>"
        for line in (
            "Ten material powstal w pipeline Ebook Factory z udzialem narzedzi AI.",
            "Tresc wymaga redakcji eksperckiej, weryfikacji zrodel i akceptacji "
            "prawnej przed publikacja lub sprzedaza.",
            f"Wygenerowano: {today}. Silnik: Ebook Factory.",
        )
    )
    return [
        ("Strona tytulowa", title_page),
        ("Spis tresci", toc),
        ("Nota o powstaniu materialu", colophon),
    ]


def publish_stage(project: Project, project_dir: Path) -> StageResult:
    chapter_paths = sorted((project_dir / "chapters").glob("chapter-*.md"))
    body_chapters = []
    for chapter_path in chapter_paths:
        title, paragraphs = _parse_chapter_markdown(chapter_path)
        body_html = "\n".join(f"<p>{html_escape(p)}</p>" for p in paragraphs)
        body_chapters.append((title, body_html))

    front = _front_matter_sections(project, [title for title, _ in body_chapters])
    title_page, toc, colophon = front
    chapters = [title_page, toc] + body_chapters + [colophon]

    pdf_path, engine = build_pdf(
        project_dir / "builds" / "book.pdf",
        title=project.title,
        chapters=chapters,
        typst_binary=_find_typst_binary(),
    )
    epub_path = build_epub(
        project_dir / "builds" / "book.epub",
        title=project.title,
        author=project.brand or "Ebook Factory",
        language=project.language,
        chapters=chapters,
    )
    engine_info = {
        "pdf_engine": engine,
        "print_grade": engine == "typst",
    }
    (project_dir / "qa" / "engine.json").write_text(
        json.dumps(engine_info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return StageResult(
        True,
        f"published with engine={engine}",
        ["builds/book.pdf", "builds/book.epub", "qa/engine.json"],
    )


def marketing_stage(project: Project, project_dir: Path) -> StageResult:
    config = MODE_CONFIG[project.mode]

    offer = (
        f"# Oferta — {project.title}\n\n"
        f"{config.label} o temacie „{project.topic}” dla {project.audience or 'wybranej grupy odbiorcow'}.\n\n"
        "## Co otrzymujesz\n"
        "- Pelny ebook w formatach PDF i EPUB\n"
        "- Okladke gotowa do publikacji\n"
        "- Materialy marketingowe (landing, posty, reklamy)\n\n"
        "*Material demonstracyjny wygenerowany automatycznie przez Ebook Factory.*\n"
    )
    (project_dir / "marketing" / "offer.md").write_text(offer, encoding="utf-8")

    landing = f"""<!DOCTYPE html>
<html lang="{project.language}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html_escape(project.title)}</title>
<meta property="og:title" content="{html_escape(project.title)}"/>
<meta property="og:description" content="{html_escape(project.topic)}"/>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: system-ui, sans-serif; background: #0b0f14; color: #f4f6f8; }}
  main {{ max-width: 720px; margin: 0 auto; padding: 48px 24px; }}
  h1 {{ font-size: clamp(28px, 5vw, 44px); line-height: 1.15; }}
  p {{ line-height: 1.6; color: #c4ccd4; }}
  .cta {{ display: inline-block; margin-top: 24px; padding: 16px 28px; background: #4f7cff;
          color: white; text-decoration: none; border-radius: 8px; font-weight: 600; }}
  .disclosure {{ margin-top: 40px; font-size: 13px; color: #8a94a0; }}
</style>
</head>
<body>
<main>
  <h1>{html_escape(project.title)}</h1>
  <p>{html_escape(project.topic)} — {html_escape(config.label)} dla {html_escape(project.audience or 'Twojej firmy')}.</p>
  <a class="cta" href="#pobierz">Pobierz teraz</a>
  <p class="disclosure">Material demonstracyjny wygenerowany przy pomocy AI w ramach pipeline Ebook Factory.</p>
</main>
</body>
</html>
"""
    (project_dir / "marketing" / "landing.html").write_text(landing, encoding="utf-8")

    posts = (
        "# Posty organiczne (DEMO)\n\n"
        f"1. Nowosc: „{project.title}” — sprawdz, jak {project.topic.lower()} zmienia codzienna prace.\n"
        f"2. Za kulisami produkcji „{project.title}” — proces, ktory mozesz powtorzyc.\n"
        f"3. 3 wnioski z „{project.title}”, ktore mozesz wdrozyc dzisiaj.\n"
    )
    (project_dir / "marketing" / "posts.md").write_text(posts, encoding="utf-8")

    ads = (
        "# Warianty reklam (DEMO)\n\n"
        f"## Wariant A\nPoznaj „{project.title}” i zacznij dzialac jeszcze dzisiaj.\n\n"
        f"## Wariant B\n{project.topic} — praktyczny przewodnik dla {project.audience or 'Twojej branzy'}.\n\n"
        f"## Wariant C\nPobierz „{project.title}” i przekonaj sie sam.\n"
    )
    (project_dir / "marketing" / "ads.md").write_text(ads, encoding="utf-8")

    return StageResult(
        True,
        "marketing assets generated",
        [
            "marketing/offer.md",
            "marketing/landing.html",
            "marketing/posts.md",
            "marketing/ads.md",
        ],
    )


def qa_stage(project: Project, project_dir: Path) -> StageResult:
    config = MODE_CONFIG[project.mode]
    checks: list[tuple[str, bool, str]] = []

    pdf_path = project_dir / "builds" / "book.pdf"
    pdf_check = check_pdf(pdf_path)
    pdf_ok = pdf_check.page_count > 0 and pdf_check.has_text
    checks.append((
        "PDF ma strony i tekst mozliwy do wyekstrahowania",
        pdf_ok,
        f"stron={pdf_check.page_count}, tekst={'tak' if pdf_check.has_text else 'nie'}, "
        f"metoda={pdf_check.method}",
    ))

    epub_path = project_dir / "builds" / "book.epub"
    epub_ok = False
    if epub_path.exists():
        import zipfile

        with zipfile.ZipFile(epub_path) as zf:
            names = set(zf.namelist())
            first = zf.infolist()[0]
            epub_ok = (
                first.filename == "mimetype"
                and "META-INF/container.xml" in names
                and any(n.endswith("content.opf") for n in names)
                and any(n.endswith("nav.xhtml") for n in names)
            )
    checks.append(("EPUB ma poprawna strukture ZIP", epub_ok, ""))

    landing_path = project_dir / "marketing" / "landing.html"
    landing_text = landing_path.read_text(encoding="utf-8") if landing_path.exists() else ""
    landing_ok = "viewport" in landing_text and "cta" in landing_text.lower()
    checks.append(("Landing ma meta viewport i CTA", landing_ok, ""))

    chapter_paths = list((project_dir / "chapters").glob("chapter-*.md"))
    outline_path = project_dir / "outline" / "outline.json"
    planned_chapters = config.chapter_count
    if outline_path.is_file():
        try:
            outline_data = json.loads(outline_path.read_text(encoding="utf-8"))
            planned_chapters = len(outline_data.get("chapters", [])) or planned_chapters
        except (OSError, json.JSONDecodeError):
            pass
    chapters_ok = len(chapter_paths) >= planned_chapters
    checks.append((
        f"Liczba rozdzialow >= {planned_chapters}",
        chapters_ok,
        f"znaleziono {len(chapter_paths)}",
    ))

    no_markers = True
    for chapter_path in chapter_paths:
        text = chapter_path.read_text(encoding="utf-8")
        if any(marker in text for marker in _TODO_MARKERS):
            no_markers = False
            break
    checks.append(("Brak oznaczen roboczych (TODO/LOREM)", no_markers, ""))

    engine_path = project_dir / "qa" / "engine.json"
    engine_info = json.loads(engine_path.read_text(encoding="utf-8")) if engine_path.exists() else {}
    engine = engine_info.get("pdf_engine", "unknown")
    print_grade = engine_info.get("print_grade", False)

    all_passed = all(passed for _, passed, _ in checks)

    lines = [f"# Raport QA — {project.title}", ""]
    for label, passed, note in checks:
        status = "PASS" if passed else "FAIL"
        suffix = f" ({note})" if note else ""
        lines.append(f"- [{status}] {label}{suffix}")
    lines.append("")
    if print_grade:
        lines.append(f"Plik ksiazki wygenerowany silnikiem **{engine}** — sklad gotowy do dalszej obrobki poligraficznej.")
    else:
        lines.append(
            f"UWAGA: plik ksiazki wygenerowany silnikiem awaryjnym **{engine}** (stdlib fallback) — "
            "jakosc podstawowa, NIE nadaje sie bezposrednio do druku."
        )

    metrics = compute_metrics(project_dir)
    lines.append("")
    lines.append("## Metryki materialu")
    lines.append("")
    lines.append(f"- Rozdzialy: {metrics['chapters']}")
    lines.append(f"- Slowa: {metrics['words']}")
    lines.append(f"- Szacowane strony (300 slow/strone): {metrics['estimated_pages']}")
    lines.append(f"- Szacowany czas czytania: {metrics['reading_minutes']} min")
    lines.append(f"- Artefakty w workspace: {metrics['artifacts']}")

    report_path = project_dir / "qa" / "qa-report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    metrics_path = project_dir / "qa" / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    message = "all checks passed" if all_passed else "one or more QA checks failed"
    return StageResult(all_passed, message, ["qa/qa-report.md", "qa/metrics.json"])


#: Files that must be present for delivery to succeed.
DELIVERY_FILENAMES = [
    "book.pdf",
    "book.epub",
    "cover.png",
    "offer.md",
    "landing.html",
    "posts.md",
    "ads.md",
    "qa-report.md",
]

#: Extra files copied when the stage that produces them ran. They enrich the
#: package (editable manuscript, structure, research trail) without becoming a
#: hard requirement for older projects resumed from disk.
OPTIONAL_DELIVERY_FILES: tuple[tuple[str, str], ...] = (
    ("manuscript.md", "builds/manuscript.md"),
    ("outline.json", "outline/outline.json"),
    ("strategy.md", "outline/strategy.md"),
    ("research-notes.md", "research/notes.md"),
    ("fact-check.md", "qa/fact-check.md"),
    ("metrics.json", "qa/metrics.json"),
    ("cover.svg", "images/cover.svg"),
)

_PACKAGE_README_TEMPLATE = """# {title}

Pakiet wyprodukowany przez Ebook Factory ({mode}).

## Co jest w srodku

| Plik | Opis |
| --- | --- |
| book.pdf | Zlozona ksiazka w PDF |
| book.epub | Wersja EPUB 3 do czytnikow |
| manuscript.md | Pelny manuskrypt w markdownie do dalszej redakcji |
| outline.json | Struktura rozdzialow uzyta przy pisaniu |
| strategy.md | Notatka strategiczna projektu |
| research-notes.md | Slad researchu do weryfikacji |
| fact-check.md | Lista twierdzen do potwierdzenia zrodlami |
| cover.png / cover.svg | Okladka w wersji rastrowej i wektorowej |
| offer.md, landing.html, posts.md, ads.md | Pakiet marketingowy |
| qa-report.md, metrics.json | Raport kontroli jakosci i metryki materialu |
| manifest.json | Sumy kontrolne SHA-256 wszystkich plikow |

## Przed publikacja

1. Zweryfikuj kazde twierdzenie z `fact-check.md` przy prawdziwym zrodle.
2. Przeprowadz redakcje jezykowa manuskryptu.
3. Sprawdz prawa do wykorzystanych materialow zrodlowych.
4. Zachowaj informacje o udziale AI w powstaniu materialu.

Wygenerowano: {generated_at}
"""


def delivery_stage(project: Project, project_dir: Path) -> StageResult:
    delivery_dir = project_dir / "delivery"
    sources = {
        "book.pdf": project_dir / "builds" / "book.pdf",
        "book.epub": project_dir / "builds" / "book.epub",
        "cover.png": project_dir / "images" / "cover.png",
        "offer.md": project_dir / "marketing" / "offer.md",
        "landing.html": project_dir / "marketing" / "landing.html",
        "posts.md": project_dir / "marketing" / "posts.md",
        "ads.md": project_dir / "marketing" / "ads.md",
        "qa-report.md": project_dir / "qa" / "qa-report.md",
    }
    for name, source in sources.items():
        shutil.copyfile(source, delivery_dir / name)

    packaged = list(DELIVERY_FILENAMES)
    for name, relative in OPTIONAL_DELIVERY_FILES:
        source = project_dir / relative
        if source.is_file():
            shutil.copyfile(source, delivery_dir / name)
            packaged.append(name)

    readme = _PACKAGE_README_TEMPLATE.format(
        title=project.title,
        mode=MODE_CONFIG[project.mode].label,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    (delivery_dir / "README.md").write_text(readme, encoding="utf-8")
    packaged.append("README.md")

    manifest = build_manifest({name: delivery_dir / name for name in packaged})
    manifest_path = delivery_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    build_delivery_zip(delivery_dir, delivery_dir / "delivery.zip", packaged + ["manifest.json"])

    artifact_paths = [f"delivery/{name}" for name in packaged]
    artifact_paths += ["delivery/manifest.json", "delivery/delivery.zip"]
    return StageResult(
        True, f"delivery package built ({len(packaged)} files)", artifact_paths
    )


DEFAULT_STAGE_HANDLERS = {
    "strategy": strategy_stage,
    "research": research_stage,
    "outline": outline_stage,
    "draft": draft_stage,
    "edit": edit_stage,
    "fact_check": fact_check_stage,
    "design": design_stage,
    "publish": publish_stage,
    "marketing": marketing_stage,
    "qa": qa_stage,
    "delivery": delivery_stage,
}
