"""Tests for the anti-AI-slop analyzer and rewriter."""

import pytest

from ebook_factory import humanize

SLOP = """# Wprowadzenie

W dzisiejszych czasach marketing treści odgrywa kluczową rolę w rozwoju każdej organizacji.
Warto pamiętać, że kompleksowe rozwiązania rewolucjonizują sposób pracy zespołów sprzedaży.
Ponadto należy podkreślić, że solidny fundament strategii jest niezwykle ważny dla zespołu.

Ponadto w dobie cyfryzacji firmy muszą dostosować podejście do zmieniających się realiów.
Co więcej, nie chodzi o narzędzia, chodzi o nawyki, procesy i ludzi w organizacji.
Dodatkowo warto zauważyć, że holistyczne podejście przynosi wymierne korzyści biznesowe.
"""

HUMAN = """# Od czego zacząć

Zacznijmy od kartki. Wypisz trzy zadania, które przesuwasz od miesiąca, i zostaw je
na wierzchu do jutra.

To wszystko.

Rano wybierz jedno z nich i ustal termin. Reszta poczeka do przeglądu w piątek, kiedy
zobaczysz, ile z tego udało się domknąć bez dokładania nowych rzeczy do listy.
"""


def test_slop_scores_far_above_human_prose():
    slop = humanize.analyze(SLOP)
    human = humanize.analyze(HUMAN)
    assert slop.ai_score > 60, slop.to_dict()
    assert human.ai_score <= humanize.HUMAN_SCORE_TARGET, human.to_dict()
    assert slop.ai_score - human.ai_score > 30


def test_analyze_names_the_specific_tells():
    codes = {finding.code for finding in humanize.analyze(SLOP).findings}
    assert {"slop_phrase", "transition_pileup", "uniform_rhythm"} <= codes


def test_humanizing_lowers_the_score_and_keeps_the_heading():
    outcome = humanize.humanize_text(SLOP, "standard")
    assert outcome.after.ai_score < outcome.before.ai_score
    assert outcome.text.startswith("# Wprowadzenie")
    assert "W dzisiejszych czasach" not in outcome.text
    assert "Warto pamiętać, że" not in outcome.text


def test_off_level_returns_the_text_untouched():
    outcome = humanize.humanize_text(SLOP, "off")
    assert outcome.text == SLOP
    assert outcome.changes == {}
    assert outcome.before.ai_score == outcome.after.ai_score


@pytest.mark.parametrize("level", humanize.HUMANIZE_LEVELS)
def test_every_level_is_deterministic(level):
    first = humanize.humanize_text(SLOP, level)
    second = humanize.humanize_text(SLOP, level)
    assert first.text == second.text


def test_stronger_levels_never_do_less_than_weaker_ones():
    light = humanize.humanize_text(SLOP, "light")
    standard = humanize.humanize_text(SLOP, "standard")
    strong = humanize.humanize_text(SLOP, "strong")
    assert sum(light.changes.values()) <= sum(standard.changes.values())
    assert sum(standard.changes.values()) <= sum(strong.changes.values())
    assert strong.after.ai_score <= light.after.ai_score


def test_unknown_level_is_rejected():
    with pytest.raises(ValueError):
        humanize.humanize_text("tekst", "turbo")


def test_markdown_structure_survives_a_rewrite():
    source = (
        "# Tytuł\n\n"
        "W dzisiejszych czasach warto pamiętać, że to działa.\n\n"
        "- pierwszy punkt listy\n"
        "- drugi punkt listy\n\n"
        "> Cytat, który zostaje na swoim miejscu.\n\n"
        "```\nkod = 'w dzisiejszych czasach'\n```\n"
    )
    text = humanize.humanize_text(source, "strong").text
    assert text.startswith("# Tytuł")
    assert "- pierwszy punkt listy" in text
    assert "> Cytat" in text
    # Code fences are untouched, even when they contain a banned phrase.
    assert "kod = 'w dzisiejszych czasach'" in text


def test_sentence_split_does_not_break_on_polish_abbreviations():
    sentences = humanize.split_sentences(
        "Zrób listę zadań, np. tych z zeszłego tygodnia. Potem wybierz jedno."
    )
    assert len(sentences) == 2


def test_long_sentences_are_split_at_a_connector():
    long_sentence = (
        "Zespół zbiera dane przez cały kwartał i analizuje je w arkuszu wspólnie z "
        "działem sprzedaży oraz działem obsługi klienta, co oznacza, że decyzja "
        "zapada dopiero po kilku tygodniach od pierwszego sygnału o problemie."
    )
    outcome = humanize.humanize_text(long_sentence, "standard")
    assert len(humanize.split_sentences(outcome.text)) > 1
    assert outcome.changes.get("long_sentence", 0) >= 1


def test_vocabulary_measure_does_not_punish_long_texts_for_being_long():
    # A text with constant local variety: every 400-token window is fully
    # distinct, but the plain type/token ratio collapses as the text grows.
    # The moving-average measure has to stay flat where the naive one does not.
    vocabulary = [f"slowo{index}" for index in range(800)]
    tokens = vocabulary * 10
    naive_ratio = len(set(tokens)) / len(tokens)

    assert naive_ratio < 0.15
    assert humanize._mattr(tokens) == pytest.approx(1.0)
    assert humanize._mattr(vocabulary[:200]) == pytest.approx(1.0)


def test_repeated_content_is_still_reported_as_thin_vocabulary():
    repeated = "\n\n".join(["Zespół zbiera dane i podejmuje decyzję w piątek."] * 60)
    assert humanize.analyze(repeated).lexical_diversity < 0.3


def test_report_serialises_for_the_api():
    payload = humanize.analyze(SLOP).to_dict()
    assert payload["ai_score"] + payload["human_score"] == 100
    assert isinstance(payload["findings"], list)
    assert {"code", "label", "severity", "count", "penalty", "hint", "measure"} <= set(
        payload["findings"][0]
    )
