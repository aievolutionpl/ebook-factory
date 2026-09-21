"""Prose composer: chapters that read like a person wrote them.

The first version of the draft stage cycled twelve fixed sentences until it hit
a word count. Every chapter came out with the same rhythm, the same openers and
the same shape — the textbook definition of AI slop.

This module composes instead of repeating. A chapter gets:

* an opening move drawn from several shapes (a scene, a blunt claim, a reader
  question, a common mistake), never the same one twice in a row;
* sections whose internal shape varies — running prose, numbered steps,
  bullets, a worked example, an aside, a contrast pair;
* a deliberate sentence rhythm: short punches between long sentences, so the
  text has burstiness rather than a metronome beat;
* a closing block with three concrete actions and one takeaway line.

Everything is deterministic. The composer is seeded from the project, so the
same project always produces the same book and a resumed run does not rewrite
history. Within one book the composer remembers what it has already used, so
chapter 9 does not echo chapter 2.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field

WRITING_STYLES: tuple[str, ...] = ("practical", "narrative", "expert")
DEFAULT_WRITING_STYLE = "practical"

WRITING_STYLE_LABELS: dict[str, str] = {
    "practical": "Praktyczny (instrukcje i checklisty)",
    "narrative": "Narracyjny (historie i przykłady)",
    "expert": "Ekspercki (analiza i argumenty)",
}

_WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*|\d+", re.UNICODE)

#: Target length of one section. Anything much smaller reads as a stub.
_WORDS_PER_SECTION = 210


def _words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _length_class(text: str) -> str:
    count = _words(text)
    if count <= 7:
        return "s"
    if count <= 16:
        return "m"
    return "l"


# --------------------------------------------------------------------------
# sentence banks
# --------------------------------------------------------------------------
# Placeholders: topic, audience, title, brand, tone, goal.
# Rule for every line below: no stock phrases, no invented statistics, and no
# two lines starting with the same word.

HOOKS: tuple[str, ...] = (
    "Zacznijmy od sytuacji, którą zna każdy, kto pracuje nad tematem: {topic}.",
    "Jest taki moment w pracy nad tym tematem, w którym wszystko się zatrzymuje.",
    "Większość osób podchodzi do tego od końca.",
    "Pierwsze pytanie brzmi: po co w ogóle się za to zabierać?",
    "Wyobraź sobie poniedziałkowy poranek i listę zadań, która nie zmieściła się na jedną kartkę.",
    "Ten rozdział nie zaczyna się od definicji, tylko od typowego błędu.",
    "Powiedzmy wprost: {goal} da się ogarnąć szybciej, niż się wydaje.",
    "Rozmowy o tym zaczynają się zwykle tak samo: od zdania „nie wiem, od czego zacząć”.",
    "Najtrudniejsza jest nie robota, tylko decyzja, co zrobić najpierw.",
    "Spójrz na to jak na remont, nie jak na projekt badawczy.",
    "Kiedy temat brzmi poważnie, łatwo zapomnieć, że ktoś musi go potem wdrożyć.",
    "Tu zaczyna się część, którą najczęściej się pomija.",
    "Dwa tygodnie. Tyle zwykle mija, zanim pierwsza wersja planu spotka się z rzeczywistością.",
    "Mała rzecz potrafi tu przesądzić o całości.",
    "Zanim padnie słowo „strategia”, warto sprawdzić, co dzisiaj naprawdę działa.",
    "Problem rzadko leży w narzędziu.",
)

CLAIMS: tuple[str, ...] = (
    "„{goal_upper}” to etap, który rozkłada się na kilka prostych ruchów.",
    "Temat „{topic}” wygląda na skomplikowany dopiero wtedy, gdy zabraknie kolejności działań.",
    "Kolejność ma tu większe znaczenie niż tempo.",
    "Sedno sprowadza się do jednego: wiedzieć, co zrobić w tym tygodniu.",
    "Dobrze poprowadzony etap oszczędza pracę na kolejnych.",
    "Ten fragment materiału dotyczy decyzji, nie teorii.",
    "Każdy z kolejnych kroków da się wykonać bez dodatkowego budżetu.",
    "Plan bez terminu jest tylko listą życzeń.",
    "Przy temacie „{topic}” najczęściej wygrywa konsekwencja, nie pomysłowość.",
    "Różnicę robi to, co dzieje się między spotkaniami.",
    "Ten materiał pisaliśmy dla jednej grupy: {audience}.",
    "Po tym rozdziale {outcome}.",
    "Jedna zmiana wprowadzona do końca jest warta więcej niż pięć rozpoczętych.",
    "Ryzyko nie polega tu na błędzie, tylko na zwlekaniu.",
    "Praktyka pokazuje, że pierwsza wersja zawsze jest za długa.",
)

MECHANISMS: tuple[str, ...] = (
    "Działa to prosto: zbierasz dane, wybierasz jeden wariant i sprawdzasz go na małej próbce.",
    "Mechanizm opiera się na powtarzalności — ten sam rytm pracy co tydzień, bez wyjątków.",
    "Najpierw ustalasz punkt odniesienia, potem zmieniasz jedną rzecz i porównujesz wynik.",
    "Pod spodem zawsze siedzi ta sama zależność: im krótsza pętla informacji zwrotnej, tym szybciej widać efekt.",
    "Cały układ trzyma się na trzech elementach: właścicielu zadania, terminie i miarze.",
    "Ważne jest rozdzielenie decyzji od wykonania, bo inaczej jedno blokuje drugie.",
    "Kiedy rozbijesz zadanie na etapy trwające po kilka godzin, przestaje ono wyglądać na projekt na kwartał.",
    "Sekwencja wygląda tak: hipoteza, mały test, wniosek, decyzja.",
    "Zapisujesz założenie, ustalasz, co je obali, i dopiero wtedy zaczynasz pracę.",
    "Czas reakcji liczy się bardziej niż jakość pierwszego podejścia.",
    "Dane bez właściciela nikomu nie pomogą.",
    "Powtarzalny proces zamienia wiedzę jednej osoby w wiedzę zespołu.",
    "Efekt kumuluje się dopiero po kilku cyklach, więc pierwszy tydzień nie jest miarodajny.",
)

FRICTIONS: tuple[str, ...] = (
    "Najczęstszy błąd to zaczynanie od narzędzia, zanim ktokolwiek zapisał cel.",
    "W tym miejscu zwykle pojawia się pokusa, żeby zrobić wszystko naraz.",
    "Projekt się sypie wtedy, gdy nikt nie odpowiada za konkretny krok.",
    "Bywa, że zespół zbiera dane przez miesiąc i nie podejmuje na ich podstawie żadnej decyzji.",
    "Blokadą rzadko bywa wiedza — częściej kalendarz.",
    "Kiedy kryteria sukcesu powstają po fakcie, każdy wynik można uznać za dobry.",
    "Zdarza się, że pierwsza wersja trafia do szuflady, bo nikt nie ustalił, kto ją zatwierdza.",
    "Trudność polega na tym, że skutki złej decyzji widać dopiero po kilku tygodniach.",
    "Uwaga: to etap, na którym najłatwiej stracić tempo.",
    "Zamiast jednej listy zadań powstają trzy, każda w innym miejscu.",
    "Nadmiar opcji kosztuje więcej niż brak opcji.",
)

PROOFS: tuple[str, ...] = (
    "Zespół, który zamienił cotygodniowy status na jedną tabelę, odzyskał godzinę tygodniowo.",
    "Przykład z praktyki: jedna osoba pilnuje terminu, druga jakości, i nikt nie pilnuje obu naraz.",
    "Weź kartkę i wypisz trzy zadania, które przesuwasz od miesiąca — to jest twoja lista startowa.",
    "Wystarczy jeden arkusz, żeby zobaczyć, gdzie zatrzymuje się praca.",
    "Kiedy zespół dostaje gotowy szablon, pierwsza wersja powstaje tego samego dnia.",
    "Prosty test: jeśli nie potrafisz opisać kroku w jednym zdaniu, jest za duży.",
    "Sprawdź to na jednym procesie, zanim obejmiesz zmianą cały zespół.",
    "Nazwij pliki tak, żeby po pół roku ktoś inny je znalazł. To wygląda na drobiazg do pierwszego audytu.",
    "Zapytaj trzy osoby, jak rozumieją cel tego etapu. Odpowiedzi rzadko się pokrywają.",
)

ACTIONS: tuple[str, ...] = (
    "Ustal jeden termin i jedną osobę odpowiedzialną, zanim przejdziesz dalej.",
    "Zrób wersję roboczą w czterdzieści minut i dopiero potem ją oceń.",
    "Zapisz kryteria, po których poznasz, że etap jest zamknięty.",
    "Wybierz jedną miarę i pilnuj jej przez miesiąc.",
    "Skróć listę do trzech pozycji. Reszta poczeka.",
    "Odłóż narzędzia do momentu, w którym proces działa na kartce.",
    "Umów krótki przegląd co tydzień, nawet na piętnaście minut.",
    "Poproś kogoś spoza zespołu o przeczytanie wniosków na świeżo.",
    "Zamknij tydzień podsumowaniem na pół strony.",
    "Zanotuj, co odpuszczasz. To równie ważne jak lista zadań.",
)

PUNCHES: tuple[str, ...] = (
    "To wszystko.",
    "Nic więcej.",
    "Tyle wystarczy na start.",
    "Prosta zasada.",
    "Działa to w obie strony.",
    "Tu nie ma skrótu.",
    "Warto to zapisać.",
    "Reszta to wykonanie.",
    "I na tym koniec.",
    "Tak wygląda punkt wyjścia.",
)

BRIDGES: tuple[str, ...] = (
    "Kolejny fragment pokazuje, jak to wygląda w tygodniowym rytmie pracy.",
    "Zostaje pytanie o kolejność, i od niego zaczyna się następna część.",
    "Dalej robi się ciekawiej, bo wchodzą w grę ludzie i terminy.",
    "Przejdźmy do miejsca, w którym plan spotyka się z kalendarzem.",
    "Na tym tle łatwiej zrozumieć kolejny krok.",
)

ASIDES: tuple[str, ...] = (
    "Jeśli masz zapamiętać z tej części jedno zdanie: zacznij od najmniejszej wersji, która działa.",
    "Notatka na marginesie: brak decyzji też jest decyzją, tylko droższą.",
    "Dobra miara jest nudna, powtarzalna i mieści się w jednej kolumnie.",
    "To miejsce, w którym warto zatrzymać się na kwadrans i zapisać własne wnioski.",
    "Jedna zasada na cały rozdział: mniejszy zakres, szybsza odpowiedź.",
)

#: Reader questions with the answer that belongs to them. Drawing the two
#: independently produced Q&A blocks where the answer had nothing to do with
#: the question — the single most obvious "a machine wrote this" tell.
QA_PAIRS: tuple[tuple[str, str], ...] = (
    (
        "Ile czasu zajmie pierwszy widoczny efekt?",
        "Zwykle kilkanaście dni, o ile zakres zostanie zawężony do jednego procesu.",
    ),
    (
        "Od czego zacząć, jeśli zespół liczy dwie osoby?",
        "Od spisania tego, co już działa. Nowe elementy dokładasz dopiero potem.",
    ),
    (
        "Co zrobić, gdy dane są niekompletne?",
        "Pracujesz na tym, co masz, i zapisujesz braki, żeby uzupełnić je w kolejnym cyklu.",
    ),
    (
        "Czy da się to wdrożyć bez zgody całej organizacji?",
        "Tak, pod warunkiem że pierwszy test obejmuje jeden zespół i jeden tydzień.",
    ),
    (
        "Jak poznać, że etap można uznać za zamknięty?",
        "Po tym, że potrafisz jednym zdaniem opisać wynik i wskazać, co robisz dalej.",
    ),
    (
        "Co zrobić, kiedy zespół nie chce zmiany?",
        "Pokazać wynik na jednym procesie zamiast przekonywać na slajdach.",
    ),
    (
        "Ile osób potrzeba do pierwszego testu?",
        "Jedna, która decyduje, i jedna, która wykonuje. Więcej na tym etapie przeszkadza.",
    ),
    (
        "Czy warto kupić narzędzie na start?",
        "Nie, dopóki proces nie działa na kartce. Narzędzie utrwala to, co już masz.",
    ),
)

STEPS: tuple[str, ...] = (
    "Spisz obecny stan w jednym miejscu, bez oceniania. Sam opis.",
    "Wybierz jeden proces, który boli najbardziej.",
    "Ustal miarę, którą sprawdzisz za tydzień.",
    "Przypisz zadanie konkretnej osobie z imienia.",
    "Przygotuj wersję roboczą i pokaż ją, zanim będzie gotowa.",
    "Zbierz uwagi w jednym dokumencie, nie w wątku e-maili.",
    "Zdecyduj, co wchodzi do kolejnej wersji, a co odpada.",
    "Zapisz wnioski tego samego dnia, póki pamiętasz szczegóły.",
    "Zaplanuj przegląd na stałą godzinę w tygodniu.",
    "Odłóż zadania, które nie mają właściciela.",
)

BULLETS: tuple[str, ...] = (
    "jeden właściciel zadania, nie komitet",
    "termin zapisany w kalendarzu, nie w głowie",
    "miara, którą da się sprawdzić w pięć minut",
    "krótka pętla informacji zwrotnej",
    "zakres mniejszy, niż podpowiada ambicja",
    "dokument, do którego wszyscy mają dostęp",
    "lista rzeczy odpuszczonych świadomie",
    "stała godzina przeglądu",
    "próbka zamiast pełnego wdrożenia",
    "wersja robocza pokazana na wczesnym etapie",
)

PITFALLS: tuple[str, ...] = (
    "zbieranie danych bez decyzji, która z nich wyniknie",
    "cel opisany tak ogólnie, że każdy wynik pasuje",
    "trzy równoległe listy zadań w trzech narzędziach",
    "przegląd przekładany do czasu „lepszego momentu”",
    "zakres rosnący po każdym spotkaniu",
    "brak osoby, która zatwierdza wersję końcową",
)

CHECKS: tuple[str, ...] = (
    "wybrać jeden proces na najbliższy tydzień",
    "zapisać miarę i miejsce, w którym ją sprawdzisz",
    "wskazać osobę odpowiedzialną z imienia",
    "ustalić termin przeglądu i wpisać go do kalendarza",
    "przygotować wersję roboczą, nawet niedoskonałą",
    "spisać, co świadomie odpuszczasz",
    "pokazać wynik komuś spoza zespołu",
)

TAKEAWAYS: tuple[str, ...] = (
    "Jedno zdanie na koniec: zawęź zakres, ustal termin, sprawdź wynik.",
    "Z tego etapu wychodzisz z jedną decyzją i jedną datą.",
    "Kiedy ten fragment zadziała, kolejny będzie krótszy.",
    "Najlepszy moment na pierwszy krok był wczoraj. Drugi najlepszy jest teraz.",
    "Tyle na tym etapie — resztę rozstrzyga wykonanie.",
)

CONTRAST_GOOD: tuple[str, ...] = (
    "jeden test na jednym zespole, zamknięty w tydzień",
    "krótka notatka z decyzją i datą",
    "miara ustalona przed startem",
)

CONTRAST_BAD: tuple[str, ...] = (
    "pełne wdrożenie od razu w całej organizacji",
    "godzinne spotkanie bez notatki",
    "ocena wyniku według kryteriów wymyślonych po fakcie",
)

SECTION_HEADS: dict[str, tuple[str, ...]] = {
    "practical": (
        "Od czego zacząć",
        "Jak to wygląda krok po kroku",
        "Gdzie to się zwykle psuje",
        "Co zrobić w tym tygodniu",
        "Szybki test na jednym procesie",
        "Czego nie robić",
        "Jak mierzyć postęp",
        "Kiedy przejść dalej",
        "Minimalna wersja, która działa",
        "Co przygotować przed startem",
        "Kto za co odpowiada",
        "Ile to zajmuje naprawdę",
        "Najtańszy sposób sprawdzenia",
        "Co zrobić, gdy brakuje czasu",
        "Praca w dwie osoby",
        "Rytm tygodnia",
    ),
    "narrative": (
        "Jak to się zaczyna",
        "Moment, w którym coś zgrzyta",
        "Co się wtedy dzieje",
        "Rozmowa, która zmienia decyzję",
        "Jak wygląda dobre zakończenie",
        "Co z tego zostaje",
        "Dzień, w którym plan się posypał",
        "Pierwsza wersja i jej los",
        "Czego nauczyła nas porażka",
        "Kiedy wreszcie zaskoczyło",
        "Widok z drugiej strony stołu",
        "Trzy miesiące później",
        "Co powiedział zespół",
        "Gdzie leżał prawdziwy problem",
        "Jak to opowiedzieć dalej",
        "Morał bez morału",
    ),
    "expert": (
        "Na czym polega problem",
        "Jak to działa pod spodem",
        "Dowody i ograniczenia",
        "Kontrargumenty",
        "Warunki brzegowe",
        "Wnioski operacyjne",
        "Co wiemy, a czego nie",
        "Dwie konkurencyjne interpretacje",
        "Koszt błędnej decyzji",
        "Jak to weryfikować",
        "Kiedy ta reguła przestaje działać",
        "Skala i jej konsekwencje",
        "Czego nie mierzy ta miara",
        "Ryzyka do wpisania w plan",
        "Praktyczne uproszczenia",
        "Co z tego wynika dla zespołu",
    ),
}

#: Section shapes. Each entry is a sequence of block renderers; a chapter never
#: uses the same shape twice.
SECTION_SHAPES: tuple[tuple[str, ...], ...] = (
    ("para", "steps", "para"),
    ("para", "bullets", "example"),
    ("example", "para", "aside"),
    ("para", "para", "checklist"),
    ("question", "para", "bullets"),
    ("para", "contrast"),
    ("para", "pitfalls", "para"),
    ("aside", "para", "steps"),
)

#: Sentence-length patterns. A paragraph picks one, which is what gives the
#: text its rhythm instead of a metronome beat.
RHYTHMS: tuple[tuple[str, ...], ...] = (
    ("l", "s", "m"),
    ("m", "m", "s"),
    ("s", "l", "m"),
    ("m", "l", "s", "m"),
    ("l", "m", "s"),
    ("s", "m", "l"),
    ("m", "s"),
    ("l", "s"),
)


@dataclass(frozen=True)
class ChapterBrief:
    """Everything the composer needs to write one chapter."""

    index: int
    title: str
    goal: str
    topic: str
    audience: str = ""
    brand: str = ""
    tone: str = ""
    style: str = DEFAULT_WRITING_STYLE
    target_words: int = 600


@dataclass
class _Bank:
    """A bank of rendered sentences, bucketed by length, served without repeats."""

    by_class: dict[str, list[str]] = field(default_factory=dict)
    used: set[str] = field(default_factory=set)

    def add(self, sentence: str) -> None:
        self.by_class.setdefault(_length_class(sentence), []).append(sentence)

    def pick(self, rng: random.Random, length_class: str) -> str:
        order = [length_class] + [c for c in ("m", "l", "s") if c != length_class]
        for candidate_class in order:
            pool = [s for s in self.by_class.get(candidate_class, []) if s not in self.used]
            if pool:
                choice = rng.choice(pool)
                self.used.add(choice)
                return choice
        # Everything has been used once; reset this bank and start over rather
        # than returning nothing.
        self.used.clear()
        pool = [s for pool_ in self.by_class.values() for s in pool_]
        if not pool:
            return ""
        choice = rng.choice(pool)
        self.used.add(choice)
        return choice


class ProseComposer:
    """Writes the chapters of one book.

    The composer is created once per draft run and reused for every chapter,
    so it can remember which sentences, section headings and shapes it has
    already spent and keep the whole book varied.
    """

    def __init__(self, seed_material: str) -> None:
        digest = hashlib.blake2b(seed_material.encode("utf-8"), digest_size=8).digest()
        self._seed = int.from_bytes(digest, "big")
        self._shape_cursor = 0
        self._head_cursor = 0
        self._banks: dict[str, _Bank] = {}
        self._context: dict[str, str] = {}
        # Spent sentences are remembered for the whole book. Banks themselves
        # are rebuilt per chapter (their text depends on the brief), but the
        # usage memory carries over, so chapter 9 does not replay chapter 2.
        self._spent: dict[str, set[str]] = {}

    # ------------------------------------------------------------------ util

    def _render(self, template: str) -> str:
        try:
            return template.format(**self._context)
        except (KeyError, IndexError):
            return template

    def _bank(self, name: str, templates: tuple[str, ...]) -> _Bank:
        bank = self._banks.get(name)
        if bank is None:
            bank = _Bank(used=self._spent.setdefault(name, set()))
            for template in templates:
                bank.add(self._render(template))
            self._banks[name] = bank
        return bank

    def _rebind(self, brief: ChapterBrief) -> None:
        goal = brief.title.strip().rstrip(".")
        outcome = (brief.goal or "").strip().rstrip(".")
        self._context = {
            "topic": brief.topic,
            "audience": brief.audience or "czytelników",
            "title": brief.title,
            "brand": brief.brand or "Ebook Factory",
            "tone": brief.tone or "rzeczowy",
            "goal": goal[:1].lower() + goal[1:] if goal else "",
            "goal_upper": goal[:1].upper() + goal[1:] if goal else "",
            "outcome": (outcome[:1].lower() + outcome[1:]) if outcome else "wiesz, co zrobić dalej",
        }
        # Rendered text depends on the brief, so banks are rebuilt per chapter;
        # the usage memory, shape cursor and heading cursor carry across.
        self._banks = {}

    # --------------------------------------------------------------- blocks

    def _paragraph(self, rng: random.Random, banks: list[tuple[str, tuple[str, ...]]]) -> str:
        rhythm = rng.choice(RHYTHMS)
        sentences: list[str] = []
        for position, length_class in enumerate(rhythm):
            name, templates = banks[position % len(banks)]
            if length_class == "s" and rng.random() < 0.45:
                name, templates = "punches", PUNCHES
            sentence = self._bank(name, templates).pick(rng, length_class)
            if sentence:
                sentences.append(sentence)
        return " ".join(sentences)

    def _distinct(
        self, rng: random.Random, name: str, templates: tuple[str, ...], count: int, cls: str
    ) -> list[str]:
        """Pick ``count`` different items. A list that repeats itself is a bug."""
        bank = self._bank(name, templates)
        items: list[str] = []
        attempts = 0
        while len(items) < count and attempts < count * 6:
            attempts += 1
            candidate = bank.pick(rng, cls)
            if candidate and candidate not in items:
                items.append(candidate)
        return items

    def _numbered(self, rng: random.Random, templates: tuple[str, ...], count: int) -> str:
        items = self._distinct(rng, "steps", templates, count, "m")
        return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))

    def _bulleted(self, rng: random.Random, name: str, templates: tuple[str, ...], count: int) -> str:
        return "\n".join(f"- {item}" for item in self._distinct(rng, name, templates, count, "s"))

    def _checklist(self, rng: random.Random, count: int) -> str:
        return "\n".join(
            f"- [ ] {item}" for item in self._distinct(rng, "checks", CHECKS, count, "s")
        )

    def _example(self, rng: random.Random) -> str:
        proof = self._bank("proofs", PROOFS).pick(rng, "m")
        follow = self._bank("mechanisms", MECHANISMS).pick(rng, "m")
        return f"**Z praktyki.** {proof} {follow}"

    def _aside(self, rng: random.Random) -> str:
        return "> " + self._bank("asides", ASIDES).pick(rng, "m")

    def _question(self, rng: random.Random) -> str:
        pairs = [pair for pair in QA_PAIRS if pair[0] not in self._spent.setdefault("qa", set())]
        if not pairs:
            self._spent["qa"].clear()
            pairs = list(QA_PAIRS)
        question, answer = rng.choice(pairs)
        self._spent["qa"].add(question)
        return f"**{question}**\n\n{answer}"

    def _contrast(self, rng: random.Random) -> str:
        good = self._bank("contrast_good", CONTRAST_GOOD).pick(rng, "s")
        bad = self._bank("contrast_bad", CONTRAST_BAD).pick(rng, "s")
        return f"**Działa:** {good}.\n\n**Nie działa:** {bad}."

    def _block(self, kind: str, rng: random.Random, style: str) -> str:
        if kind == "steps":
            return self._numbered(rng, STEPS, rng.randint(3, 4))
        if kind == "bullets":
            return self._bulleted(rng, "bullets", BULLETS, rng.randint(3, 4))
        if kind == "pitfalls":
            heading = "Na co uważać:"
            return heading + "\n\n" + self._bulleted(rng, "pitfalls", PITFALLS, 3)
        if kind == "checklist":
            return self._checklist(rng, 3)
        if kind == "example":
            return self._example(rng)
        if kind == "aside":
            return self._aside(rng)
        if kind == "question":
            return self._question(rng)
        if kind == "contrast":
            return self._contrast(rng)
        return self._paragraph(rng, self._paragraph_banks(style))

    @staticmethod
    def _paragraph_banks(style: str) -> list[tuple[str, tuple[str, ...]]]:
        if style == "narrative":
            return [
                ("proofs", PROOFS),
                ("frictions", FRICTIONS),
                ("claims", CLAIMS),
                ("mechanisms", MECHANISMS),
            ]
        if style == "expert":
            return [
                ("mechanisms", MECHANISMS),
                ("claims", CLAIMS),
                ("frictions", FRICTIONS),
                ("actions", ACTIONS),
            ]
        return [
            ("claims", CLAIMS),
            ("actions", ACTIONS),
            ("mechanisms", MECHANISMS),
            ("frictions", FRICTIONS),
        ]

    # -------------------------------------------------------------- chapters

    def _next_shape(self, rng: random.Random) -> tuple[str, ...]:
        shape = SECTION_SHAPES[self._shape_cursor % len(SECTION_SHAPES)]
        self._shape_cursor += 1
        return shape

    def _next_heading(self, style: str) -> str:
        heads = SECTION_HEADS.get(style, SECTION_HEADS[DEFAULT_WRITING_STYLE])
        head = heads[self._head_cursor % len(heads)]
        self._head_cursor += 1
        return head

    def compose_chapter(self, brief: ChapterBrief) -> str:
        """Return one chapter as markdown, at roughly ``brief.target_words``."""
        self._rebind(brief)
        rng = random.Random(self._seed ^ (brief.index * 0x9E3779B1))

        parts: list[str] = [f"# {brief.title}", ""]
        opening = self._bank("hooks", HOOKS).pick(rng, "m")
        follow = self._bank("claims", CLAIMS).pick(rng, "l")
        punch = self._bank("punches", PUNCHES).pick(rng, "s")
        parts.append(f"{opening} {follow} {punch}".strip())
        parts.append("")

        budget = max(160, brief.target_words)
        # Sections are sized, not counted: a section shorter than ~200 words
        # turns the chapter into a list of headings, which is exactly the shape
        # readers skim past.
        section_count = max(2, min(6, round(budget / _WORDS_PER_SECTION)))
        section_budget = budget / section_count

        for section in range(section_count):
            parts.append(f"## {self._next_heading(brief.style)}")
            parts.append("")
            shape = list(self._next_shape(rng))
            written_here = 0
            position = 0
            while written_here < section_budget * 0.85 and position < 10:
                if position >= len(shape):
                    # Out of blocks: take a different arrangement rather than
                    # replaying this one, which would read as a loop.
                    shape += [kind for kind in self._next_shape(rng) if kind not in shape[-2:]]
                    if position >= len(shape):
                        break
                block = self._block(shape[position], rng, brief.style)
                position += 1
                if not block:
                    continue
                parts.append(block)
                parts.append("")
                written_here += _words(block)
            if section < section_count - 1 and section % 2 == 1:
                bridge = self._bank("bridges", BRIDGES).pick(rng, "m")
                if bridge:
                    parts.append(bridge)
                    parts.append("")

        parts.append("## Zanim przejdziesz dalej")
        parts.append("")
        parts.append(self._checklist(rng, 3))
        parts.append("")
        parts.append(self._bank("takeaways", TAKEAWAYS).pick(rng, "m"))
        parts.append("")

        text = "\n".join(parts)
        return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def compose_preface(title: str, topic: str, audience: str, chapters: list[str]) -> str:
    """A short, honest opening for the manuscript — not a wall of boilerplate."""
    first = chapters[0] if chapters else "pierwszego rozdziału"
    last = chapters[-1] if chapters else "ostatniego rozdziału"
    reader_line = f"Odbiorca: {audience}.\n\n" if audience else ""
    return (
        "## Jak czytać tę książkę\n\n"
        f"Materiał prowadzi przez temat „{topic}” od {first.lower()} do {last.lower()}. "
        "Każdy rozdział kończy się trzema zadaniami do odhaczenia — to one decydują "
        "o tym, czy lektura cokolwiek zmieni.\n\n"
        f"{reader_line}"
        "Rozdziały da się czytać po kolei albo wyrywkowo. Jeśli masz mało czasu, "
        "zacznij od list kontrolnych i wróć do reszty później.\n\n"
        f"Książkę „{title}” złożył pipeline Ebook Factory z udziałem narzędzi AI. "
        "Przed publikacją przejdź redakcję merytoryczną i zweryfikuj źródła.\n"
    )


__all__ = [
    "ChapterBrief",
    "DEFAULT_WRITING_STYLE",
    "ProseComposer",
    "WRITING_STYLES",
    "WRITING_STYLE_LABELS",
    "compose_preface",
]
