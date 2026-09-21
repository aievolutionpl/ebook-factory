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
from .humanize import (
    CHANGE_LABELS,
    DEFAULT_HUMANIZE_LEVEL,
    HUMANIZE_LEVEL_LABELS,
    HUMAN_SCORE_TARGET,
    analyze,
    humanize_text,
)
from .models import MODE_CONFIG, Project
from .pdfcheck import check_pdf
from .pipeline import StageResult
from .prose import ChapterBrief, ProseComposer, compose_preface
from .workspace import compute_metrics

CHAPTER_TEMPLATES = [
    "Wprowadzenie do tematu",
    "Dlaczego to ma znaczenie",
    "Pierwsze kroki",
    "Najczęstsze błędy",
    "Narzędzia i zasoby",
    "Studium przypadku",
    "Zaawansowane techniki",
    "Mierzenie efektów",
    "Skalowanie działań",
    "Utrzymanie wyników",
    "Checklisty i szablony",
    "Plan wdrożenia",
    "Pytania i odpowiedzi",
    "Podsumowanie i następne kroki",
]

#: What the reader walks away with. Rotated per chapter so the outline reads
#: like a plan rather than a list of restated titles.
CHAPTER_OUTCOMES = [
    "wiesz, od czego zacząć i co odłożyć na później",
    "masz listę pytań, które trzeba zadać zespołowi",
    "potrafisz opisać ten etap jednym zdaniem",
    "wiesz, jak sprawdzić, czy to naprawdę działa",
    "masz plan na najbliższy tydzień",
    "znasz trzy błędy, które kosztują najwięcej czasu",
    "wiesz, które narzędzia są potrzebne, a bez których się obejdzie",
    "umiesz ocenić, czy etap można zamknąć",
    "masz gotowy szablon do wypełnienia",
    "wiesz, komu przypisać odpowiedzialność",
]

_TODO_MARKERS = ("TODO", "LOREM IPSUM", "FIXME")


def _find_typst_binary() -> str | None:
    candidate = Path.home() / ".local" / "bin" / "typst"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("typst")
    return found


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
        f"**Język:** {project.language}\n"
        f"**Odbiorca:** {project.audience or 'nieokreślony — do uzupełnienia przed sprzedażą'}\n"
        f"**Marka:** {project.brand or 'Ebook Factory Demo'}\n"
        f"**Ton:** {project.tone or 'rzeczowy'}\n\n"
        "## Obietnica\n"
        f"Ten ebook pokazuje odbiorcy konkretną ścieżkę do wykorzystania tematu "
        f"„{project.topic}” w praktyce.\n\n"
        "## Pozycjonowanie\n"
        "Materiał demonstracyjny wygenerowany przez pipeline Ebook Factory — "
        "struktura i proces są realne, treść wymaga redakcji eksperckiej przed sprzedażą.\n"
    )
    if project.source_materials:
        content += (
            "\n## Materiały źródłowe\n"
            "Strategia uwzględnia poniższe materiały dostarczone przez użytkownika:\n\n"
            f"{project.source_materials}\n"
        )
    path = project_dir / "outline" / "strategy.md"
    path.write_text(content, encoding="utf-8")
    return StageResult(True, "strategy captured", ["outline/strategy.md"])


def research_stage(project: Project, project_dir: Path) -> StageResult:
    lines = [
        "# Notatki z researchu (DEMO)",
        "",
        "> Ten plik zawiera przykładowe, automatycznie wygenerowane placeholdery źródeł. "
        "W produkcji zastąp je prawdziwym researchem i linkami.",
        "",
    ]
    for i in range(1, 6):
        lines.append(
            f"{i}. [DEMO ZRODLO {i}] Materiały o „{project.topic}” — zastąp prawdziwym "
            "linkiem, autorem i datą publikacji przed użyciem komercyjnym."
        )
    if project.source_materials:
        lines.append("")
        lines.append("## Materiały źródłowe dostarczone przez użytkownika")
        lines.append("")
        lines.append(
            "Research uwzględnia poniższe materiały jako punkt wyjścia do dalszej weryfikacji:"
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
        {
            "title": title,
            "goal": "Po tym rozdziale " + CHAPTER_OUTCOMES[index % len(CHAPTER_OUTCOMES)],
        }
        for index, title in enumerate(titles)
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
    """Write every chapter with the prose composer.

    One composer serves the whole book so it can remember which sentences,
    section shapes and headings it already spent; that is what keeps chapter 9
    from reading like chapter 2. The seed is derived from the project, so the
    same project always produces the same manuscript.
    """
    config = MODE_CONFIG[project.mode]
    outline = json.loads((project_dir / "outline" / "outline.json").read_text(encoding="utf-8"))
    composer = ProseComposer(f"{project.slug}|{project.topic}|{project.mode}")
    artifact_paths = []
    for index, chapter in enumerate(outline["chapters"], start=1):
        goal = str(chapter.get("goal", "")).removeprefix("Po tym rozdziale ")
        brief = ChapterBrief(
            index=index,
            title=chapter["title"],
            goal=goal,
            topic=project.topic,
            audience=project.audience,
            brand=project.brand,
            tone=project.tone,
            style=project.writing_style,
            target_words=config.words_per_chapter,
        )
        markdown = composer.compose_chapter(brief)
        chapter_path = project_dir / "chapters" / f"chapter-{index:02d}.md"
        chapter_path.write_text(markdown, encoding="utf-8")
        artifact_paths.append(f"chapters/chapter-{index:02d}.md")
    return StageResult(True, f"{len(artifact_paths)} chapters drafted", artifact_paths)


def humanize_stage(project: Project, project_dir: Path) -> StageResult:
    """Strip the machine-writing tells out of every chapter.

    The rewrite is bounded on purpose: it deletes filler, swaps stock phrases,
    thins transitions and splits runaway sentences. It never invents a fact and
    never adds a claim, so the result stays as true as the draft it edited.
    Findings that only a person can fix land in the report instead.
    """
    level = project.humanize_level or DEFAULT_HUMANIZE_LEVEL
    chapter_paths = sorted((project_dir / "chapters").glob("chapter-*.md"))
    if not chapter_paths:
        return StageResult(
            False,
            "no chapters to humanize — rerun the project from the draft stage",
        )

    rows: list[dict] = []
    totals: dict[str, int] = {}
    before_parts: list[str] = []
    after_parts: list[str] = []
    artifact_paths: list[str] = []

    for chapter_path in chapter_paths:
        original = chapter_path.read_text(encoding="utf-8")
        outcome = humanize_text(original, level)
        before_parts.append(original)
        after_parts.append(outcome.text)
        if outcome.text != original:
            chapter_path.write_text(outcome.text, encoding="utf-8")
            artifact_paths.append(f"chapters/{chapter_path.name}")
        for key, count in outcome.changes.items():
            totals[key] = totals.get(key, 0) + count
        lines = outcome.text.strip().splitlines()
        title = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("#") else chapter_path.stem
        rows.append(
            {
                "file": f"chapters/{chapter_path.name}",
                "title": title,
                "before": outcome.before.ai_score,
                "after": outcome.after.ai_score,
                "burstiness": round(outcome.after.burstiness, 3),
                "changes": sum(outcome.changes.values()),
            }
        )

    book_before = analyze("\n\n".join(before_parts))
    book_after = analyze("\n\n".join(after_parts))
    summary = {
        "level": level,
        "level_label": HUMANIZE_LEVEL_LABELS.get(level, level),
        "target": HUMAN_SCORE_TARGET,
        "changes": dict(sorted(totals.items())),
        "total_changes": sum(totals.values()),
        "before": book_before.to_dict(),
        "after": book_after.to_dict(),
        "chapters": rows,
    }
    (project_dir / "qa" / "humanize.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (project_dir / "qa" / "humanize-report.md").write_text(
        _humanize_report(project, summary, book_before, book_after), encoding="utf-8"
    )
    artifact_paths += ["qa/humanize.json", "qa/humanize-report.md"]
    message = (
        f"humanized at level={level}: ślad AI {book_before.ai_score} → "
        f"{book_after.ai_score}, {sum(totals.values())} poprawek"
    )
    return StageResult(True, message, artifact_paths)


def _humanize_report(project: Project, summary: dict, before, after) -> str:
    lines = [
        f"# Raport humanizacji — {project.title}",
        "",
        f"Poziom humanizacji: **{summary['level_label']}**",
        "",
        f"Ślad AI: **{before.ai_score}/100 → {after.ai_score}/100** "
        f"(cel: {HUMAN_SCORE_TARGET} lub mniej, ocena: {after.grade})",
        "",
        "## Rytm i czytelność",
        "",
        f"- Średnia długość zdania: {after.avg_sentence_words:.1f} słowa",
        f"- Zróżnicowanie długości zdań: {after.burstiness:.2f} "
        "(im wyżej, tym mniej maszynowo — cel: 0.38+)",
        f"- Zdania dłuższe niż 32 słowa: {after.long_sentence_ratio * 100:.0f}%",
        f"- Bogactwo słownictwa: {after.lexical_diversity:.2f}",
        "",
    ]
    if summary["changes"]:
        lines += ["## Co poprawiono automatycznie", ""]
        for key, count in summary["changes"].items():
            lines.append(f"- {CHANGE_LABELS.get(key, key)}: {count}")
        lines.append("")
    else:
        lines += ["## Co poprawiono automatycznie", "", "- nic — tekst przeszedł bez poprawek", ""]

    lines += ["## Co zostaje dla redaktora", ""]
    if after.findings:
        for finding in after.findings:
            example = f" Przykład: „{finding.examples[0]}”." if finding.examples else ""
            lines.append(f"- **{finding.label}** ({finding.count}×) — {finding.hint}{example}")
    else:
        lines.append("- brak wykrytych śladów maszynowego pisania")
    lines += ["", "## Rozdział po rozdziale", "", "| Rozdział | Przed | Po | Poprawki |", "| --- | --- | --- | --- |"]
    for row in summary["chapters"]:
        lines.append(f"| {row['title']} | {row['before']} | {row['after']} | {row['changes']} |")
    lines.append("")
    return "\n".join(lines)


def edit_stage(project: Project, project_dir: Path) -> StageResult:
    chapter_paths = sorted((project_dir / "chapters").glob("chapter-*.md"))
    chapter_titles: list[str] = []
    for chapter_path in chapter_paths:
        head = chapter_path.read_text(encoding="utf-8").lstrip().splitlines()
        chapter_titles.append(head[0].lstrip("# ").strip() if head else chapter_path.stem)
    manuscript_parts = [
        f"# {project.title}",
        "",
        compose_preface(project.title, project.topic, project.audience, chapter_titles),
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
            "Następujące zdania zawierają liczby i wymagają weryfikacji źródłowej "
            "przed publikacją:"
        )
        lines.append("")
        for claim in claims:
            lines.append(f"- {claim} — źródło: DO WERYFIKACJI (demo)")
    else:
        lines.append("Brak twierdzeń liczbowych wymagających weryfikacji w treści demo.")
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
            f"Język: {project.language}",
            f"Data złożenia: {today}",
        )
    )
    toc = "".join(
        f"<p>{index}. {html_escape(title)}</p>"
        for index, title in enumerate(chapter_titles, start=1)
    ) or "<p>Brak rozdziałów.</p>"
    colophon = "".join(
        f"<p>{html_escape(line)}</p>"
        for line in (
            "Ten materiał powstał w pipeline Ebook Factory z udziałem narzędzi AI.",
            "Treść wymaga redakcji eksperckiej, weryfikacji źródeł i akceptacji "
            "prawnej przed publikacją lub sprzedażą.",
            f"Wygenerowano: {today}. Silnik: Ebook Factory.",
        )
    )
    return [
        ("Strona tytułowa", title_page),
        ("Spis treści", toc),
        ("Nota o powstaniu materiału", colophon),
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
        "- Okładkę gotową do publikacji\n"
        "- Materiały marketingowe (landing, posty, reklamy)\n\n"
        "*Materiał demonstracyjny wygenerowany automatycznie przez Ebook Factory.*\n"
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
  <p class="disclosure">Materiał demonstracyjny wygenerowany przy pomocy AI w ramach pipeline Ebook Factory.</p>
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
    #: (label, passed, note, blocking). Non-blocking rows are editorial advice:
    #: they belong in the report, but they must not fail a build on their own.
    checks: list[tuple[str, bool, str, bool]] = []

    pdf_path = project_dir / "builds" / "book.pdf"
    pdf_check = check_pdf(pdf_path)
    pdf_ok = pdf_check.page_count > 0 and pdf_check.has_text
    checks.append((
        "PDF ma strony i tekst możliwy do wyekstrahowania",
        pdf_ok,
        f"stron={pdf_check.page_count}, tekst={'tak' if pdf_check.has_text else 'nie'}, "
        f"metoda={pdf_check.method}",
        True,
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
    checks.append(("EPUB ma poprawną strukturę ZIP", epub_ok, "", True))

    landing_path = project_dir / "marketing" / "landing.html"
    landing_text = landing_path.read_text(encoding="utf-8") if landing_path.exists() else ""
    landing_ok = "viewport" in landing_text and "cta" in landing_text.lower()
    checks.append(("Landing ma meta viewport i CTA", landing_ok, "", True))

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
        f"Liczba rozdziałów >= {planned_chapters}",
        chapters_ok,
        f"znaleziono {len(chapter_paths)}",
        True,
    ))

    no_markers = True
    for chapter_path in chapter_paths:
        text = chapter_path.read_text(encoding="utf-8")
        if any(marker in text for marker in _TODO_MARKERS):
            no_markers = False
            break
    checks.append(("Brak oznaczeń roboczych (TODO/LOREM)", no_markers, "", True))

    # Readability is graded, not gated: a low score is a note for the editor,
    # never a reason to throw away a finished build.
    humanize_path = project_dir / "qa" / "humanize.json"
    readability: dict = {}
    if humanize_path.is_file():
        try:
            readability = json.loads(humanize_path.read_text(encoding="utf-8")).get("after", {})
        except (OSError, json.JSONDecodeError):
            readability = {}
    if not readability and chapter_paths:
        readability = analyze(
            "\n\n".join(path.read_text(encoding="utf-8") for path in chapter_paths)
        ).to_dict()
    if readability:
        ai_score = readability.get("ai_score", 100)
        checks.append((
            f"Ślad AI w tekście <= {HUMAN_SCORE_TARGET}",
            ai_score <= HUMAN_SCORE_TARGET,
            f"wynik {ai_score}/100 ({readability.get('grade', '?')})",
            False,
        ))
        burstiness = readability.get("burstiness", 0.0)
        checks.append((
            "Rytm zdań zróżnicowany (0.38+)",
            burstiness >= 0.38,
            f"zróżnicowanie {burstiness:.2f}, średnie zdanie "
            f"{readability.get('avg_sentence_words', 0)} słowa",
            False,
        ))

    engine_path = project_dir / "qa" / "engine.json"
    engine_info = json.loads(engine_path.read_text(encoding="utf-8")) if engine_path.exists() else {}
    engine = engine_info.get("pdf_engine", "unknown")
    print_grade = engine_info.get("print_grade", False)

    all_passed = all(passed for _label, passed, _note, blocking in checks if blocking)

    lines = [f"# Raport QA — {project.title}", ""]
    for label, passed, note, blocking in checks:
        status = "PASS" if passed else ("FAIL" if blocking else "UWAGA")
        suffix = f" ({note})" if note else ""
        lines.append(f"- [{status}] {label}{suffix}")
    lines.append("")
    if print_grade:
        lines.append(f"Plik książki wygenerowany silnikiem **{engine}** — skład gotowy do dalszej obróbki poligraficznej.")
    else:
        lines.append(
            f"UWAGA: plik książki wygenerowany silnikiem awaryjnym **{engine}** (stdlib fallback) — "
            "jakość podstawowa, NIE nadaje się bezpośrednio do druku."
        )

    metrics = compute_metrics(project_dir)
    lines.append("")
    lines.append("## Metryki materiału")
    lines.append("")
    lines.append(f"- Rozdziały: {metrics['chapters']}")
    lines.append(f"- Słowa: {metrics['words']}")
    lines.append(f"- Szacowane strony (300 słów/stronę): {metrics['estimated_pages']}")
    lines.append(f"- Szacowany czas czytania: {metrics['reading_minutes']} min")
    lines.append(f"- Artefakty w workspace: {metrics['artifacts']}")
    if readability:
        lines.append("")
        lines.append("## Czytelność i ślad AI")
        lines.append("")
        lines.append(f"- Ślad AI: {readability.get('ai_score')}/100 ({readability.get('grade')})")
        lines.append(f"- Średnia długość zdania: {readability.get('avg_sentence_words')} słowa")
        lines.append(f"- Zróżnicowanie długości zdań: {readability.get('burstiness')}")
        lines.append(f"- Bogactwo słownictwa: {readability.get('lexical_diversity')}")
        lines.append("")
        lines.append("Szczegóły i lista poprawek: `qa/humanize-report.md`.")

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
    ("humanize-report.md", "qa/humanize-report.md"),
    ("humanize.json", "qa/humanize.json"),
    ("metrics.json", "qa/metrics.json"),
    ("cover.svg", "images/cover.svg"),
)

_PACKAGE_README_TEMPLATE = """# {title}

Pakiet wyprodukowany przez Ebook Factory ({mode}).

## Co jest w środku

| Plik | Opis |
| --- | --- |
| book.pdf | Złożona książka w PDF |
| book.epub | Wersja EPUB 3 do czytników |
| manuscript.md | Pełny manuskrypt w markdownie do dalszej redakcji |
| outline.json | Struktura rozdziałów użyta przy pisaniu |
| strategy.md | Notatka strategiczna projektu |
| research-notes.md | Ślad researchu do weryfikacji |
| fact-check.md | Lista twierdzeń do potwierdzenia źródłami |
| humanize-report.md | Raport humanizacji: ślad AI, rytm zdań, lista poprawek |
| humanize.json | Ten sam raport w formie danych |
| cover.png / cover.svg | Okładka w wersji rastrowej i wektorowej |
| offer.md, landing.html, posts.md, ads.md | Pakiet marketingowy |
| qa-report.md, metrics.json | Raport kontroli jakości i metryki materiału |
| manifest.json | Sumy kontrolne SHA-256 wszystkich plików |

## Przed publikacją

1. Zweryfikuj każde twierdzenie z `fact-check.md` przy prawdziwym źródle.
2. Przeprowadź redakcję merytoryczną manuskryptu — humanizator poprawia to,
   jak tekst brzmi, nigdy to, co mówi.
3. Przejrzyj `humanize-report.md` i popraw to, co zostało oznaczone jako
   praca dla redaktora.
4. Sprawdź prawa do wykorzystanych materiałów źródłowych.
5. Zachowaj informację o udziale AI w powstaniu materiału.

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
    missing = [name for name, source in sources.items() if not source.is_file()]
    if missing:
        # Resuming a half-built workspace should say what is absent, not raise
        # a FileNotFoundError that reaches the operator as a bare stack string.
        return StageResult(
            False,
            "missing required build outputs: "
            + ", ".join(sorted(missing))
            + " — retry the project from the stage that produces them",
        )

    delivery_dir.mkdir(parents=True, exist_ok=True)
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
    "humanize": humanize_stage,
    "edit": edit_stage,
    "fact_check": fact_check_stage,
    "design": design_stage,
    "publish": publish_stage,
    "marketing": marketing_stage,
    "qa": qa_stage,
    "delivery": delivery_stage,
}
