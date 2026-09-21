"""Anti-AI-slop humanizer: detect machine-writing tells and rewrite them away.

Two jobs live here and they are deliberately separate.

``analyze()`` reads text and reports *why* it sounds machine-made: banned
phrases, filler openers, transition pile-ups, em-dash spray, hedging, and the
statistical tells (uniform sentence rhythm, uniform paragraph length, repeated
sentence openers, thin vocabulary). It never changes anything.

``humanize_text()`` rewrites what can be rewritten safely and deterministically:
it deletes filler, swaps stock phrases for plain ones, thins transitions,
tames em dashes, splits runaway sentences and breaks up flat rhythm. It never
invents facts, never adds a sentence with new claims, and always keeps markdown
structure (headings, lists, quotes, code fences) intact.

Everything is deterministic: the same input and level always produce the same
output, which keeps the pipeline resumable and the tests honest.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

#: Rewrite strength, from weakest to strongest.
HUMANIZE_LEVELS: tuple[str, ...] = ("off", "light", "standard", "strong")
DEFAULT_HUMANIZE_LEVEL = "standard"

HUMANIZE_LEVEL_LABELS: dict[str, str] = {
    "off": "Wyłączony",
    "light": "Lekki",
    "standard": "Standardowy",
    "strong": "Mocny",
}

#: Score at or below which a text is considered publication-ready prose.
HUMAN_SCORE_TARGET = 35

_MAX_SENTENCE_WORDS = 32
_STRONG_MAX_SENTENCE_WORDS = 26
_EM_DASH_PER_1000 = 4.0
_MIN_BURSTINESS = 0.38

_ABBREVIATIONS = {
    "np", "itd", "itp", "tj", "tzn", "ok", "dr", "prof", "inż", "mgr",
    "godz", "ul", "str", "mln", "tys", "wg", "ds", "por", "red", "zob",
    "etc", "vs", "mr", "dr",
}

_WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*|\d+(?:[.,]\d+)*", re.UNICODE)
_SENTENCE_END_RE = re.compile(r"[.!?…]+[\"'”»)\]]*")
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002190-\U000021FF\U00002600-\U000027BF\U0000FE0F\U00002B00-\U00002BFF]"
)


# --------------------------------------------------------------------------
# stock-phrase rules
# --------------------------------------------------------------------------

def _rule(pattern: str, replacement: str) -> tuple[re.Pattern[str], str]:
    return re.compile(pattern, re.IGNORECASE), replacement


#: Phrases that mark text as machine-written, with a plain replacement.
#: An empty replacement means "delete it, the sentence is better without".
SLOP_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    # Polish opening padding
    _rule(r"\bw dzisiejszych czasach\b,?\s*", "dziś "),
    _rule(r"\bw dzisiejszym świecie\b,?\s*", "dziś "),
    _rule(r"\bw dobie (?:cyfryzacji|internetu|sztucznej inteligencji|AI)\b,?\s*", ""),
    _rule(r"\bw erze (?:cyfrowej|sztucznej inteligencji|AI)\b,?\s*", ""),
    _rule(r"\bw obecnych realiach\b,?\s*", ""),
    _rule(r"\bw szybko zmieniającym się świecie\b,?\s*", ""),
    _rule(r"\bw dynamicznie zmieniającej się rzeczywistości\b,?\s*", ""),
    _rule(r"\bżyjemy w czasach,? w których\b\s*", ""),
    # Polish filler connectives
    _rule(r"\bwarto (?:pamiętać|zauważyć|podkreślić|zaznaczyć|nadmienić),? że\b\s*", ""),
    _rule(r"\bnależy (?:pamiętać|zauważyć|podkreślić|zaznaczyć),? że\b\s*", ""),
    _rule(r"\bnie da się ukryć,? że\b\s*", ""),
    _rule(r"\bnie ulega wątpliwości,? że\b\s*", ""),
    _rule(r"\bjak (?:już )?wspomniano (?:wcześniej|powyżej)\b,?\s*", ""),
    _rule(r"\bjak powszechnie wiadomo\b,?\s*", ""),
    _rule(r"\bw rzeczywistości\b,?\s*", ""),
    _rule(r"\bgeneralnie rzecz biorąc\b,?\s*", ""),
    _rule(r"\bw gruncie rzeczy\b,?\s*", ""),
    _rule(r"\bw pewnym sensie\b,?\s*", ""),
    _rule(r"\btak naprawdę\b,?\s*", ""),
    _rule(r"\bw zasadzie\b,?\s*", ""),
    _rule(r"\bco (?:istotne|ważne|ciekawe),?\s*", ""),
    _rule(r"\brzecz jasna\b,?\s*", ""),
    _rule(r"\bbez wątpienia\b,?\s*", ""),
    _rule(r"\bniewątpliwie\b\s*", ""),
    _rule(r"\bz całą pewnością\b\s*", ""),
    # Polish inflated vocabulary. Every swap keeps the grammatical case of the
    # surrounding sentence: either an adjective is dropped whole, or the
    # replacement carries the same ending as the word it stands in for.
    _rule(r"\brewolucjonizuje\b", "zmienia"),
    _rule(r"\brewolucjonizują\b", "zmieniają"),
    _rule(r"\brewolucjonizujemy\b", "zmieniamy"),
    _rule(r"\bprzełomow(y|a|e|ego|ej|ym|ych)\b", r"now\1"),
    _rule(r"\bkompleksow(?:y|a|e|ego|ej|ym|ych|emu|ą)\s+", ""),
    _rule(r"\bsolidn(?:y|a|e|ego|ej|ym|ych|ą)\s+(?=fundament|podstaw|bazę)", ""),
    _rule(r"\bkluczow(?:y|a|e) (?:jest|są),?\s+(?:aby|by)\b", "trzeba"),
    _rule(r"\bodgrywa kluczową rolę w\b", "decyduje o"),
    _rule(r"\bstanowi nieodłączny element\b", "należy do"),
    _rule(r"\bw sposób (?:znaczący|istotny)\b(?!\s+(?:i|oraz|a)\b)", "wyraźnie"),
    _rule(r"\bnieocenion(?:y|ym|a|ą|e)\s+", ""),
    _rule(r"\bszeroki wachlarz\b", "wiele"),
    _rule(r"\bcały szereg\b", "kilka"),
    _rule(r"\bholistyczn(e|y|a|ym|ego|ej|ych)\b", r"całościow\1"),
    _rule(r"\bdedykowan(y|a|e|ym|ego|ej|ych)\b", r"osobn\1"),
    _rule(r"\bproaktywnie\b", "z wyprzedzeniem"),
    # Polish conversational AI tics
    _rule(r"\bzanurzmy się w\b", "wejdźmy w"),
    _rule(r"\bzagłębmy się w\b", "wejdźmy w"),
    _rule(r"\bodkryjmy (?:razem|wspólnie)\b", "sprawdźmy"),
    _rule(r"\bmam nadzieję,? że (?:ten|ta|to)\b[^.]*\.\s*", ""),
    _rule(r"\bw niniejszym (?:rozdziale|artykule|materiale)\b", "tutaj"),
    _rule(r"\bpodsumowując powyższe rozważania\b,?\s*", "Krótko: "),
    _rule(r"\bmając powyższe na uwadze\b,?\s*", ""),
    _rule(r"\bpamiętaj,? że kluczem (?:jest|do sukcesu jest)\b", "Najważniejsze jest"),
    # English tells that leak into mixed-language drafts
    _rule(r"\bdelve into\b", "dig into"),
    _rule(r"\bit'?s worth noting that\b\s*", ""),
    _rule(r"\bit is important to note that\b\s*", ""),
    _rule(r"\bin today'?s (?:fast[- ]paced )?world\b,?\s*", ""),
    _rule(r"\bin the ever[- ]evolving landscape of\b", "in"),
    _rule(r"\bgame[- ]chang(er|ing)\b", "big shift"),
    _rule(r"\bleverage\b", "use"),
    _rule(r"\butilize\b", "use"),
    _rule(r"\bseamless(?:ly)?\b", "smoothly"),
    _rule(r"\brobust\b", "solid"),
    _rule(r"\bcutting[- ]edge\b", "new"),
    _rule(r"\bunlock the (?:full )?potential of\b", "get more out of"),
    _rule(r"\bembark on (?:a|this) journey\b", "start"),
    _rule(r"\bnavigate the complexities of\b", "handle"),
    _rule(r"\ba testament to\b", "proof of"),
    _rule(r"\bin conclusion\b,?\s*", ""),
    _rule(r"\bfurthermore\b,?\s*", ""),
    _rule(r"\bmoreover\b,?\s*", ""),
)

#: Sentence-initial padding that adds nothing. Removed, then the sentence is
#: re-capitalised.
FILLER_OPENERS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^oczywiście,\s*",
        r"^jak wiadomo,\s*",
        r"^rzecz w tym,? że\s*",
        r"^prawda jest taka,? że\s*",
        r"^istotne jest,? (?:aby|by|że)\s*",
        r"^ważne jest,? (?:aby|by|że)\s*",
        r"^trzeba przyznać,? że\s*",
        r"^można powiedzieć,? że\s*",
        r"^wydaje się,? że\s*",
        r"^jak się okazuje,\s*",
        r"^co więcej,\s*",
        r"^warto dodać,? że\s*",
    )
)

#: Paragraph-initial connectors. One or two in a chapter reads fine; six in a
#: row is the classic machine cadence, so the extras get dropped.
TRANSITION_OPENERS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^ponadto,?\s+",
        r"^dodatkowo,?\s+",
        r"^co więcej,?\s+",
        r"^co istotne,?\s+",
        r"^w konsekwencji,?\s+",
        r"^w rezultacie,?\s+",
        r"^z drugiej strony,?\s+",
        r"^jednocześnie,?\s+",
        r"^niemniej jednak,?\s+",
        r"^w efekcie,?\s+",
        r"^reasumując,?\s+",
        r"^podsumowując,?\s+",
    )
)

_HEDGES = (
    "może", "chyba", "prawdopodobnie", "zazwyczaj", "zwykle", "raczej",
    "niejako", "poniekąd", "pewnego rodzaju", "swego rodzaju", "generalnie",
)
_BOOSTERS = (
    "absolutnie", "zdecydowanie", "dosłownie", "niesamowicie", "niezwykle",
    "ogromnie", "rewelacyjnie", "fantastycznie", "kluczowo", "definitywnie",
    "naprawdę", "wręcz", "niezaprzeczalnie",
)
_ANTITHESIS_RE = re.compile(
    r"\bnie (?:chodzi o|jest to|tylko)\b[^.!?]{0,80}?\b(?:chodzi o|ale (?:także|też|również)|to)\b",
    re.IGNORECASE,
)
_TRIAD_RE = re.compile(
    r"\b[\wąćęłńóśźż]+,\s+[\wąćęłńóśźż]+\s+(?:i|oraz)\s+[\wąćęłńóśźż]+\b",
    re.IGNORECASE,
)

_SPLIT_CONNECTORS = (
    ", a jednocześnie ", ", a zarazem ", ", natomiast ", ", podczas gdy ",
    ", co oznacza, że ", ", co sprawia, że ", ", dzięki czemu ", ", ale ",
    ", a ", ", oraz ", ", przy czym ",
)


# --------------------------------------------------------------------------
# report objects
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Finding:
    """One detected tell, with enough detail for an operator to act on it."""

    code: str
    label: str
    severity: str
    count: int
    penalty: int
    hint: str
    examples: tuple[str, ...] = ()
    #: Set for signals that measure the whole text rather than counting hits;
    #: ``count`` is 1 for those, so a UI shows the measurement, not "1×".
    measure: str = ""

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "label": self.label,
            "severity": self.severity,
            "count": self.count,
            "penalty": self.penalty,
            "hint": self.hint,
            "measure": self.measure,
            "examples": list(self.examples),
        }


@dataclass
class TextReport:
    """Statistical fingerprint of a piece of prose plus its AI tells."""

    ai_score: int
    grade: str
    words: int
    sentences: int
    paragraphs: int
    avg_sentence_words: float
    burstiness: float
    long_sentence_ratio: float
    lexical_diversity: float
    paragraph_variety: float
    findings: list[Finding] = field(default_factory=list)

    @property
    def human_enough(self) -> bool:
        return self.ai_score <= HUMAN_SCORE_TARGET

    def to_dict(self) -> dict:
        return {
            "ai_score": self.ai_score,
            "human_score": 100 - self.ai_score,
            "grade": self.grade,
            "human_enough": self.human_enough,
            "words": self.words,
            "sentences": self.sentences,
            "paragraphs": self.paragraphs,
            "avg_sentence_words": round(self.avg_sentence_words, 1),
            "burstiness": round(self.burstiness, 3),
            "long_sentence_ratio": round(self.long_sentence_ratio, 3),
            "lexical_diversity": round(self.lexical_diversity, 3),
            "paragraph_variety": round(self.paragraph_variety, 3),
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class HumanizeOutcome:
    """Result of a rewrite: the new text, what changed, and before/after scores."""

    text: str
    level: str
    changes: dict[str, int]
    before: TextReport
    after: TextReport

    @property
    def changed(self) -> bool:
        return sum(self.changes.values()) > 0

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "changed": self.changed,
            "changes": dict(sorted(self.changes.items())),
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "improvement": self.before.ai_score - self.after.ai_score,
        }


# --------------------------------------------------------------------------
# markdown-aware block handling
# --------------------------------------------------------------------------

@dataclass
class _Block:
    kind: str  # "prose" | "heading" | "list" | "quote" | "code" | "blank"
    prefix: str
    text: str


_LIST_RE = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+(?:\[[ xX]\]\s+)?)(.*)$")
_QUOTE_RE = re.compile(r"^(\s*>\s?)(.*)$")
_HEADING_RE = re.compile(r"^(\s*#{1,6}\s+)(.*)$")


def _parse_blocks(text: str) -> list[_Block]:
    blocks: list[_Block] = []
    in_code = False
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(_Block("prose", "", " ".join(paragraph)))
            paragraph.clear()

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush()
            in_code = not in_code
            blocks.append(_Block("code", "", line))
            continue
        if in_code:
            blocks.append(_Block("code", "", line))
            continue
        if not stripped:
            flush()
            blocks.append(_Block("blank", "", ""))
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            flush()
            blocks.append(_Block("heading", heading.group(1), heading.group(2)))
            continue
        item = _LIST_RE.match(line)
        if item:
            flush()
            blocks.append(_Block("list", item.group(1), item.group(2)))
            continue
        quote = _QUOTE_RE.match(line)
        if quote:
            flush()
            blocks.append(_Block("quote", quote.group(1), quote.group(2)))
            continue
        if stripped.startswith("|") or stripped.startswith("---"):
            flush()
            blocks.append(_Block("code", "", line))
            continue
        paragraph.append(stripped)

    flush()
    return blocks


def _render_blocks(blocks: list[_Block]) -> str:
    lines: list[str] = []
    for block in blocks:
        if block.kind == "blank":
            lines.append("")
        elif block.kind == "code":
            lines.append(block.text)
        else:
            lines.append((block.prefix + block.text).rstrip())
    return "\n".join(lines)


# --------------------------------------------------------------------------
# text primitives
# --------------------------------------------------------------------------

def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, without tripping over Polish abbreviations."""
    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_END_RE.finditer(text):
        end = match.end()
        head = text[start:end]
        token = re.split(r"[\s(]", head.strip())[-1].rstrip(".!?…\"'”»)]").lower()
        if token in _ABBREVIATIONS:
            continue
        if end < len(text) and not text[end : end + 1].isspace():
            continue
        candidate = head.strip()
        if candidate:
            sentences.append(candidate)
        start = end
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _capitalize(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1 :]
        if char not in "\"'„“«(-–— ":
            return text
    return text


def _starts_lowercase(text: str) -> bool:
    for char in text:
        if char.isalpha():
            return char.islower()
    return False


def _lower_first(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.lower() + text[index + 1 :]
    return text


def _tidy(text: str) -> str:
    """Repair the punctuation left behind after deletions."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,;:])\s*([,.;:])", r"\2", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"^[,;:\s]+", "", text)
    return text.strip()


def _recapitalize(text: str) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return text
    return " ".join(_capitalize(sentence) for sentence in sentences)


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------

def _prose_of(blocks: list[_Block]) -> list[str]:
    return [b.text for b in blocks if b.kind in ("prose", "list", "quote") and b.text.strip()]


def _cv(values: list[int]) -> float:
    """Coefficient of variation: how much the lengths actually differ."""
    usable = [v for v in values if v > 0]
    if len(usable) < 2:
        return 1.0
    mean = statistics.fmean(usable)
    if mean == 0:
        return 1.0
    return statistics.pstdev(usable) / mean


def _mattr(tokens: list[str], window: int = 400) -> float:
    """Moving-average type-token ratio.

    A plain type/token ratio falls as a text grows, so a long book would always
    look impoverished next to a short one. Averaging the ratio over a sliding
    window of fixed size makes the number comparable between a lead magnet and
    a 300-page book.
    """
    if not tokens:
        return 1.0
    if len(tokens) <= window:
        return len(set(tokens)) / len(tokens)
    ratios = []
    step = max(1, window // 4)
    for start in range(0, len(tokens) - window + 1, step):
        chunk = tokens[start : start + window]
        ratios.append(len(set(chunk)) / window)
    return statistics.fmean(ratios) if ratios else 1.0


def _finding(
    code: str,
    label: str,
    severity: str,
    count: int,
    penalty: int,
    hint: str,
    examples: list[str] | None = None,
    measure: str = "",
) -> Finding:
    unique: list[str] = []
    for example in examples or []:
        snippet = " ".join(example.split())[:120]
        if snippet and snippet not in unique:
            unique.append(snippet)
        if len(unique) == 3:
            break
    return Finding(code, label, severity, count, penalty, hint, tuple(unique), measure)


def _grade(score: int) -> str:
    if score <= 15:
        return "ludzki"
    if score <= HUMAN_SCORE_TARGET:
        return "prawie ludzki"
    if score <= 60:
        return "wyczuwalny szablon"
    return "maszynowy"


def analyze(text: str) -> TextReport:
    """Score a piece of markdown prose for machine-writing tells."""
    blocks = _parse_blocks(text)
    prose_blocks = _prose_of(blocks)
    prose = " ".join(prose_blocks)
    headings = [b.text for b in blocks if b.kind == "heading"]
    paragraphs = [b.text for b in blocks if b.kind == "prose" and b.text.strip()]

    sentences = split_sentences(prose)
    sentence_lengths = [count_words(s) for s in sentences]
    words = count_words(prose)
    per_1000 = (words / 1000) or 1.0

    findings: list[Finding] = []

    def add(code, label, severity, count, penalty, hint, examples=None, measure="") -> None:
        if count > 0 and penalty > 0:
            findings.append(
                _finding(code, label, severity, count, penalty, hint, examples, measure)
            )

    # --- stock phrases -----------------------------------------------------
    phrase_hits: list[str] = []
    for pattern, _replacement in SLOP_PHRASES:
        phrase_hits.extend(match.group(0).strip() for match in pattern.finditer(prose))
    add(
        "slop_phrase",
        "Zwroty-wytrychy typowe dla AI",
        "high",
        len(phrase_hits),
        min(22, round(len(phrase_hits) / per_1000 * 3)),
        "Zamień je na konkret albo usuń — nic nie wnoszą.",
        phrase_hits,
    )

    # --- filler openers ----------------------------------------------------
    filler_hits = [
        sentence
        for sentence in sentences
        if any(pattern.match(sentence) for pattern in FILLER_OPENERS)
    ]
    add(
        "filler_opener",
        "Zdania zaczynające się od waty",
        "medium",
        len(filler_hits),
        min(12, round(len(filler_hits) / per_1000 * 4)),
        "Zacznij od rzeczy, o której piszesz, nie od zapowiedzi.",
        filler_hits,
    )

    # --- transition pile-up ------------------------------------------------
    transition_hits = [
        paragraph
        for paragraph in paragraphs
        if any(pattern.match(paragraph) for pattern in TRANSITION_OPENERS)
    ]
    ratio = len(transition_hits) / len(paragraphs) if paragraphs else 0.0
    add(
        "transition_pileup",
        "Akapity zaczynane łącznikiem (Ponadto, Co więcej…)",
        "medium",
        len(transition_hits),
        min(10, round(max(0.0, ratio - 0.15) * 40)),
        "Najwyżej co czwarty akapit powinien zaczynać się łącznikiem.",
        transition_hits,
    )

    # --- em dashes ---------------------------------------------------------
    em_dashes = prose.count("—") + prose.count(" – ")
    excess = max(0.0, em_dashes / per_1000 - _EM_DASH_PER_1000)
    add(
        "em_dash",
        "Nadmiar myślników",
        "medium",
        em_dashes,
        min(8, round(excess * 1.5)),
        "Część myślników zamień na przecinek albo kropkę.",
    )

    # --- antithesis and triads ---------------------------------------------
    antithesis = [m.group(0) for m in _ANTITHESIS_RE.finditer(prose)]
    add(
        "antithesis",
        "Konstrukcja „nie X, tylko Y”",
        "medium",
        len(antithesis),
        min(8, round(len(antithesis) / per_1000 * 4)),
        "Napisz wprost, co jest prawdą — bez budowania kontrastu.",
        antithesis,
    )
    triads = [m.group(0) for m in _TRIAD_RE.finditer(prose)]
    triad_rate = len(triads) / per_1000
    add(
        "triad",
        "Wyliczenia po trzy",
        "low",
        len(triads),
        min(6, round(max(0.0, triad_rate - 4) * 1.2)),
        "Rozbij część trójek na dwa elementy albo na listę.",
        triads,
    )

    # --- hedging and boosters ----------------------------------------------
    hedge_count = sum(
        len(re.findall(rf"\b{re.escape(word)}\b", prose, re.IGNORECASE)) for word in _HEDGES
    )
    add(
        "hedging",
        "Asekuracja (może, zazwyczaj, raczej…)",
        "low",
        hedge_count,
        min(8, round(max(0.0, hedge_count / per_1000 - 8) * 0.8)),
        "Napisz, co wiesz na pewno, a resztę oznacz jako hipotezę.",
    )
    booster_count = sum(
        len(re.findall(rf"\b{re.escape(word)}\b", prose, re.IGNORECASE)) for word in _BOOSTERS
    )
    add(
        "booster",
        "Wzmacniacze bez pokrycia (absolutnie, niezwykle…)",
        "low",
        booster_count,
        min(6, round(booster_count / per_1000 * 2)),
        "Usuń przysłówek albo zastąp go liczbą.",
    )

    # --- rhythm ------------------------------------------------------------
    burstiness = _cv(sentence_lengths)
    add(
        "uniform_rhythm",
        "Zdania o niemal identycznej długości",
        "high",
        1,
        min(18, round(max(0.0, _MIN_BURSTINESS - burstiness) * 60)),
        "Wpleć kilka zdań krótkich (3-6 słów) między długie.",
        measure=f"zróżnicowanie {burstiness:.2f} (cel: {_MIN_BURSTINESS}+)",
    )

    long_sentences = [s for s, length in zip(sentences, sentence_lengths) if length > _MAX_SENTENCE_WORDS]
    long_ratio = len(long_sentences) / len(sentences) if sentences else 0.0
    add(
        "long_sentences",
        "Zdania dłuższe niż 32 słowa",
        "medium",
        len(long_sentences),
        min(10, round(max(0.0, long_ratio - 0.08) * 60)),
        "Podziel je w miejscu spójnika.",
        long_sentences,
    )

    paragraph_variety = _cv([count_words(p) for p in paragraphs])
    add(
        "uniform_paragraphs",
        "Akapity równej długości",
        "medium",
        1,
        min(8, round(max(0.0, 0.32 - paragraph_variety) * 30)),
        "Zostaw jeden akapit jednozdaniowy, inny rozbuduj.",
        measure=f"zróżnicowanie {paragraph_variety:.2f} (cel: 0.32+)",
    )

    openers: dict[str, int] = {}
    for sentence in sentences:
        first = _WORD_RE.findall(sentence)
        if first:
            key = first[0].lower()
            openers[key] = openers.get(key, 0) + 1
    # A long book will always repeat common openers; only a share above what
    # ordinary prose uses counts as a tell, so the threshold scales with length.
    opener_budget = max(3, round(0.04 * len(sentences)))
    repeated = {
        word: n - opener_budget
        for word, n in openers.items()
        if n > opener_budget and len(word) > 2
    }
    excess = sum(repeated.values())
    add(
        "repeated_openers",
        "Powtarzane początki zdań",
        "medium",
        excess,
        min(10, round(excess / len(sentences) * 60)) if sentences else 0,
        "Zmień szyk zdania albo zacznij od czasownika.",
        [
            f"„{word}” ponad limit o {n}"
            for word, n in sorted(repeated.items(), key=lambda kv: -kv[1])
        ],
    )

    # --- vocabulary --------------------------------------------------------
    tokens = [t.lower() for t in _WORD_RE.findall(prose)]
    diversity = _mattr(tokens)
    add(
        "low_diversity",
        "Ubogie słownictwo",
        "medium",
        1,
        min(10, round(max(0.0, 0.62 - diversity) * 45)) if len(tokens) > 200 else 0,
        "Powtarzane rzeczowniki zastąp konkretami z tematu.",
        measure=f"różnorodność {diversity:.2f} (cel: 0.62+)",
    )

    # --- surface noise -----------------------------------------------------
    exclamations = prose.count("!")
    add(
        "exclamation",
        "Wykrzykniki",
        "low",
        exclamations,
        min(4, round(max(0, exclamations - 1) * 0.8)),
        "W tekście użytkowym jeden wykrzyknik to maksimum.",
    )
    emojis = len(_EMOJI_RE.findall(text))
    add(
        "emoji",
        "Emoji w tekście książki",
        "low",
        emojis,
        min(4, emojis),
        "Usuń je z treści rozdziału.",
    )
    title_case = [
        heading
        for heading in headings
        if len([w for w in heading.split() if w[:1].isupper()]) >= 3
    ]
    add(
        "title_case_heading",
        "Nagłówki pisane Wielkimi Literami",
        "low",
        len(title_case),
        min(4, len(title_case)),
        "Po polsku nagłówek zapisuje się zdaniowo.",
        title_case,
    )

    score = min(100, sum(f.penalty for f in findings))
    findings.sort(key=lambda f: (-f.penalty, f.code))
    return TextReport(
        ai_score=score,
        grade=_grade(score),
        words=words,
        sentences=len(sentences),
        paragraphs=len(paragraphs),
        avg_sentence_words=statistics.fmean(sentence_lengths) if sentence_lengths else 0.0,
        burstiness=burstiness,
        long_sentence_ratio=long_ratio,
        lexical_diversity=diversity,
        paragraph_variety=paragraph_variety,
        findings=findings,
    )


# --------------------------------------------------------------------------
# rewriting
# --------------------------------------------------------------------------

def _replace_phrases(text: str, counter: dict[str, int]) -> str:
    for pattern, replacement in SLOP_PHRASES:
        def _repl(match: re.Match[str], replacement=replacement) -> str:
            counter["slop_phrase"] = counter.get("slop_phrase", 0) + 1
            try:
                out = match.expand(replacement) if "\\" in replacement else replacement
            except (re.error, IndexError):
                out = replacement
            if out and match.group(0)[:1].isupper():
                out = _capitalize(out)
            return out

        text = pattern.sub(_repl, text)
    return text


def _strip_filler_openers(text: str, counter: dict[str, int]) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return text
    out: list[str] = []
    for sentence in sentences:
        rewritten = sentence
        for pattern in FILLER_OPENERS:
            new = pattern.sub("", rewritten, count=1)
            if new != rewritten:
                counter["filler_opener"] = counter.get("filler_opener", 0) + 1
                rewritten = new
                break
        out.append(_capitalize(_tidy(rewritten)) if rewritten else rewritten)
    return " ".join(s for s in out if s)


def _tame_em_dashes(text: str, counter: dict[str, int], budget: int) -> str:
    def _walk(value: str) -> str:
        parts = value.split("—")
        if len(parts) <= budget + 1:
            return value
        rebuilt = parts[0]
        for index, part in enumerate(parts[1:], start=1):
            if index <= budget:
                rebuilt += "—" + part
            else:
                counter["em_dash"] = counter.get("em_dash", 0) + 1
                joined = rebuilt.rstrip() + "," + part
                rebuilt = re.sub(r",\s+(i|oraz|a)\s", r" \1 ", joined, count=1)
        return rebuilt

    return _walk(text)


def _split_long_sentences(text: str, counter: dict[str, int], limit: int) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return text
    out: list[str] = []
    for sentence in sentences:
        if count_words(sentence) <= limit:
            out.append(sentence)
            continue
        split_at = -1
        connector = ""
        for candidate in _SPLIT_CONNECTORS:
            position = sentence.find(candidate, 20)
            if position != -1 and (split_at == -1 or position < split_at):
                split_at = position
                connector = candidate
        if split_at == -1:
            out.append(sentence)
            continue
        head = sentence[:split_at].strip()
        tail = sentence[split_at + len(connector) :].strip()
        if count_words(head) < 5 or count_words(tail) < 5:
            out.append(sentence)
            continue
        counter["long_sentence"] = counter.get("long_sentence", 0) + 1
        if not head.endswith((".", "!", "?")):
            head += "."
        out.append(head)
        out.append(_capitalize(tail))
    return " ".join(out)


def _drop_repeated_openers(text: str, counter: dict[str, int]) -> str:
    sentences = split_sentences(text)
    if len(sentences) < 2:
        return text
    seen: set[str] = set()
    out: list[str] = []
    for sentence in sentences:
        words = _WORD_RE.findall(sentence)
        key = words[0].lower() if words else ""
        rewritten = sentence
        if key and key in seen:
            for pattern in TRANSITION_OPENERS:
                new = pattern.sub("", rewritten, count=1)
                if new != rewritten:
                    counter["repeated_opener"] = counter.get("repeated_opener", 0) + 1
                    rewritten = _capitalize(_tidy(new))
                    break
        if key:
            seen.add(key)
        out.append(rewritten)
    return " ".join(out)


def _thin_transitions(blocks: list[_Block], counter: dict[str, int], keep: int) -> None:
    kept = 0
    for block in blocks:
        if block.kind != "prose":
            continue
        for pattern in TRANSITION_OPENERS:
            if pattern.match(block.text):
                if kept < keep:
                    kept += 1
                    break
                stripped = pattern.sub("", block.text, count=1)
                if count_words(stripped) >= 4:
                    counter["transition"] = counter.get("transition", 0) + 1
                    block.text = _capitalize(_tidy(stripped))
                break


def _thin_sentence_transitions(text: str, counter: dict[str, int]) -> str:
    """Drop connectors that open a sentence inside a paragraph.

    The first sentence keeps whatever it has — that is the paragraph's own
    opener, handled separately. Every following "Ponadto"/"Niemniej jednak"
    is padding that a person would not have typed.
    """
    sentences = split_sentences(text)
    if len(sentences) < 2:
        return text
    out = [sentences[0]]
    for sentence in sentences[1:]:
        rewritten = sentence
        for pattern in TRANSITION_OPENERS:
            stripped = pattern.sub("", rewritten, count=1)
            if stripped != rewritten and count_words(stripped) >= 4:
                counter["transition"] = counter.get("transition", 0) + 1
                rewritten = _capitalize(_tidy(stripped))
                break
        out.append(rewritten)
    return " ".join(out)


def _punch_up(blocks: list[_Block], counter: dict[str, int]) -> None:
    """Give flat paragraphs a short sentence so the rhythm stops being metronomic."""
    for block in blocks:
        if block.kind != "prose":
            continue
        sentences = split_sentences(block.text)
        if len(sentences) < 3:
            continue
        lengths = [count_words(s) for s in sentences]
        if min(lengths) <= 9 or _cv(lengths) >= _MIN_BURSTINESS:
            continue
        longest = max(range(len(sentences)), key=lambda i: lengths[i])
        rewritten = _split_long_sentences(sentences[longest], counter, limit=10)
        if rewritten != sentences[longest]:
            counter["rhythm"] = counter.get("rhythm", 0) + 1
            sentences[longest] = rewritten
            block.text = " ".join(sentences)


_BOOSTER_RE = re.compile(
    r"\s*\b(?:" + "|".join(_BOOSTERS) + r")\b\s*", re.IGNORECASE
)


def _trim_boosters(text: str, counter: dict[str, int]) -> str:
    """Drop empty intensifiers. They are adverbs, so the sentence survives."""
    hits = len(_BOOSTER_RE.findall(text))
    if not hits:
        return text
    counter["booster"] = counter.get("booster", 0) + hits
    return _tidy(_BOOSTER_RE.sub(" ", text))


def _normalize_exclamations(text: str, counter: dict[str, int]) -> str:
    if text.count("!") <= 1:
        return text
    first = text.find("!")
    head, tail = text[: first + 1], text[first + 1 :]
    counter["exclamation"] = counter.get("exclamation", 0) + tail.count("!")
    return head + tail.replace("!", ".")


def _strip_emoji(text: str, counter: dict[str, int]) -> str:
    hits = len(_EMOJI_RE.findall(text))
    if not hits:
        return text
    counter["emoji"] = counter.get("emoji", 0) + hits
    return _tidy(_EMOJI_RE.sub("", text))


def humanize_text(text: str, level: str = DEFAULT_HUMANIZE_LEVEL) -> HumanizeOutcome:
    """Rewrite ``text`` so it reads like a person wrote it.

    ``level`` selects how much is allowed to change:

    ``off``       analysis only, the text comes back untouched;
    ``light``     stock phrases, emoji and exclamation spam;
    ``standard``  the above plus filler openers, transition pile-ups, em-dash
                  spray and runaway sentences;
    ``strong``    the above plus rhythm repair and repeated sentence openers,
                  with a tighter sentence-length ceiling.
    """
    if level not in HUMANIZE_LEVELS:
        raise ValueError(f"unknown humanize level {level!r}; expected one of {HUMANIZE_LEVELS}")

    before = analyze(text)
    if level == "off":
        return HumanizeOutcome(text, level, {}, before, before)

    counter: dict[str, int] = {}
    blocks = _parse_blocks(text)
    strong = level == "strong"
    standard = level in ("standard", "strong")
    limit = _STRONG_MAX_SENTENCE_WORDS if strong else _MAX_SENTENCE_WORDS
    dash_budget = 1 if strong else 2

    for block in blocks:
        if block.kind in ("blank", "code"):
            continue
        # A bullet written as a lower-case fragment is a style choice, not a
        # mistake; the rewriter must not turn a list into a set of sentences.
        was_lowercase = _starts_lowercase(block.text)
        working = _strip_emoji(block.text, counter)
        working = _replace_phrases(working, counter)
        working = _normalize_exclamations(working, counter)
        if block.kind != "heading":
            if standard:
                working = _strip_filler_openers(working, counter)
                working = _tame_em_dashes(working, counter, dash_budget)
                working = _split_long_sentences(working, counter, limit)
            if strong:
                working = _thin_sentence_transitions(working, counter)
                working = _trim_boosters(working, counter)
                working = _drop_repeated_openers(working, counter)
        block.text = _tidy(working)
        if block.kind == "prose":
            block.text = _recapitalize(block.text)
        if was_lowercase:
            block.text = _lower_first(block.text)

    if standard:
        _thin_transitions(blocks, counter, keep=1)
    if strong:
        _punch_up(blocks, counter)

    rewritten = _render_blocks(blocks)
    rewritten = re.sub(r"\n{3,}", "\n\n", rewritten).strip() + "\n"
    after = analyze(rewritten)
    return HumanizeOutcome(rewritten, level, counter, before, after)


CHANGE_LABELS: dict[str, str] = {
    "slop_phrase": "wymienione zwroty-wytrychy",
    "filler_opener": "usunięte początki-waty",
    "transition": "usunięte łączniki na starcie akapitu",
    "em_dash": "myślniki zamienione na przecinki",
    "long_sentence": "podzielone zdania-molochy",
    "repeated_opener": "rozbite powtarzane początki zdań",
    "rhythm": "wyrównany rytm akapitu",
    "booster": "usunięte wzmacniacze bez pokrycia",
    "exclamation": "zdjęte wykrzykniki",
    "emoji": "usunięte emoji",
}


__all__ = [
    "CHANGE_LABELS",
    "DEFAULT_HUMANIZE_LEVEL",
    "Finding",
    "HUMANIZE_LEVELS",
    "HUMANIZE_LEVEL_LABELS",
    "HUMAN_SCORE_TARGET",
    "HumanizeOutcome",
    "TextReport",
    "analyze",
    "count_words",
    "humanize_text",
    "split_sentences",
]
