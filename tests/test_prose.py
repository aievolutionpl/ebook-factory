"""Tests for the chapter composer: variety, rhythm and determinism."""

import pytest

from ebook_factory import humanize
from ebook_factory.prose import (
    WRITING_STYLES,
    ChapterBrief,
    ProseComposer,
    compose_preface,
)

TITLES = [
    "Wprowadzenie do tematu",
    "Najczęstsze błędy",
    "Narzędzia i zasoby",
    "Plan wdrożenia",
]


def _brief(index: int, title: str, **overrides) -> ChapterBrief:
    data = dict(
        index=index,
        title=title,
        goal="wiesz, od czego zacząć i co sprawdzić w tym tygodniu",
        topic="automatyzacja sprzedaży",
        audience="właścicieli małych firm",
        brand="Acme",
        tone="rzeczowy",
        target_words=600,
    )
    data.update(overrides)
    return ChapterBrief(**data)


def _book(style: str = "practical") -> list[str]:
    composer = ProseComposer("seed|temat")
    return [
        composer.compose_chapter(_brief(index, title, style=style))
        for index, title in enumerate(TITLES, start=1)
    ]


def test_chapter_hits_its_word_budget():
    chapter = ProseComposer("seed|temat").compose_chapter(_brief(1, TITLES[0]))
    words = humanize.count_words(chapter)
    assert 480 <= words <= 900, words


def test_chapter_starts_with_its_own_title_and_closes_with_actions():
    chapter = ProseComposer("seed|temat").compose_chapter(_brief(1, TITLES[0]))
    assert chapter.startswith(f"# {TITLES[0]}")
    assert "## Zanim przejdziesz dalej" in chapter
    assert "- [ ] " in chapter


def test_composition_is_deterministic():
    assert _book() == _book()


def test_different_projects_produce_different_books():
    first = ProseComposer("alfa|temat").compose_chapter(_brief(1, TITLES[0]))
    second = ProseComposer("beta|inny temat").compose_chapter(_brief(1, TITLES[0]))
    assert first != second


def test_chapters_do_not_repeat_each_other():
    chapters = _book()
    assert len(set(chapters)) == len(chapters)
    headings = [
        line for chapter in chapters for line in chapter.splitlines() if line.startswith("## ")
    ]
    closing = "## Zanim przejdziesz dalej"
    varied = [heading for heading in headings if heading != closing]
    # Headings rotate through the bank, so a short book never repeats one.
    assert len(set(varied)) == len(varied)
    # And no chapter repeats a heading inside itself.
    for chapter in chapters:
        own = [line for line in chapter.splitlines() if line.startswith("## ")]
        assert len(set(own)) == len(own), own


@pytest.mark.parametrize("style", WRITING_STYLES)
def test_every_style_reads_as_human_written(style):
    for chapter in _book(style):
        report = humanize.analyze(chapter)
        assert report.ai_score <= humanize.HUMAN_SCORE_TARGET, (style, report.to_dict())
        assert report.burstiness >= 0.38, (style, report.burstiness)


def test_prose_varies_sentence_length_instead_of_marching():
    chapter = ProseComposer("seed|temat").compose_chapter(_brief(1, TITLES[0]))
    lengths = [humanize.count_words(s) for s in humanize.split_sentences(chapter)]
    assert min(lengths) <= 7, lengths
    assert max(lengths) >= 15, lengths


def test_chapters_mix_block_shapes_not_just_paragraphs():
    chapter = "\n".join(_book())
    assert "1. " in chapter          # numbered steps
    assert "\n- " in chapter          # bullets
    assert "\n> " in chapter          # aside
    assert "**" in chapter            # example / contrast lead-ins


def test_preface_names_the_first_and_last_chapter():
    preface = compose_preface("Tytuł", "temat", "właścicieli firm", TITLES)
    assert TITLES[0].lower() in preface
    assert TITLES[-1].lower() in preface
    assert "AI" in preface


def test_sections_are_long_enough_to_be_worth_a_heading():
    chapter = ProseComposer("seed|temat").compose_chapter(_brief(1, TITLES[0]))
    blocks = chapter.split("\n## ")
    # Intro plus the sections; every section carries real text, not a stub.
    body_sections = blocks[1:-1]
    assert body_sections
    for section in body_sections:
        assert humanize.count_words(section) >= 90, section


def test_question_blocks_pair_the_answer_with_its_question():
    from ebook_factory.prose import QA_PAIRS

    text = "\n".join(_book("practical") + _book("expert"))
    answers = {question: answer for question, answer in QA_PAIRS}
    for question, answer in answers.items():
        if f"**{question}**" in text:
            index = text.index(f"**{question}**")
            following = text[index : index + len(question) + len(answer) + 20]
            assert answer in following, question


def test_a_list_never_repeats_an_item_inside_one_block():
    for chapter in _book():
        current: list[str] = []
        for line in chapter.splitlines() + [""]:
            if line.startswith("- ") or line.startswith("- [ ] "):
                current.append(line)
                continue
            if current:
                assert len(set(current)) == len(current), current
                current = []


def test_audience_is_only_used_where_polish_grammar_allows_it():
    # A free-text audience cannot be inflected, so it may only appear after a
    # colon or in a label — never as the subject of a generated sentence.
    from ebook_factory import prose

    banks = [
        prose.HOOKS, prose.CLAIMS, prose.MECHANISMS, prose.FRICTIONS,
        prose.PROOFS, prose.ACTIONS, prose.PUNCHES, prose.BRIDGES,
        prose.ASIDES, prose.STEPS, prose.BULLETS, prose.CHECKS,
        prose.TAKEAWAYS, prose.PITFALLS,
    ]
    for bank in banks:
        for template in bank:
            if "{audience}" in template:
                head = template.split("{audience}")[0]
                assert head.rstrip().endswith(":"), template
