# Ebook Factory — projekt systemu

## Cel
Prywatna fabryka produkcji ebooków pod sprzedaż. Użytkownik podaje temat i parametry w panelu webowym. System automatycznie wykonuje research, plan, pisanie, redakcję, kontrolę faktów, skład, eksport i przygotowanie materiałów sprzedażowych. Publikacja pozostaje ręczna.

## Zakres MVP

### Tryby produkcji
- Lead magnet: 15–30 stron.
- Poradnik ekspercki: 40–100 stron.
- Książka premium: 150–300 stron.

### Wejście
- temat,
- tryb produkcji,
- język,
- odbiorca,
- marka,
- ton,
- opcjonalne materiały źródłowe.

### Wyjście
Folder `delivery/` zawierający:
- PDF,
- EPUB,
- okładkę PNG,
- opis oferty,
- landing page,
- posty organiczne,
- warianty reklam,
- raport QA,
- manifest plików.

## Architektura

### Panel webowy
Responsywny interfejs mobile/tablet-first. Ekrany: dashboard projektów, formularz nowego projektu, szczegóły produkcji, log etapów, artefakty i pobieranie paczki. Duże przyciski, kontrast WCAG AA, statusy tekstowe i kolorystyczne.

### Backend
Python + FastAPI. SQLite przechowuje projekty, etapy, zdarzenia i artefakty. Worker wykonuje kolejne etapy, zapisując stan po każdym z nich. Produkcja może zostać wznowiona od pierwszego nieukończonego etapu.

### Pipeline
1. Strategia: odbiorca, obietnica, pozycjonowanie.
2. Research: źródła i notatki.
3. Architektura: spis treści, cele rozdziałów, budżet stron.
4. Draft: treść rozdziałów.
5. Redakcja: struktura, styl, powtórzenia, anti-slop.
6. Fact-check: lista twierdzeń i źródeł.
7. Design: okładka i ilustracje.
8. Publikacja: Typst PDF oraz EPUB.
9. Marketing: oferta, landing page, posty i reklamy.
10. QA: testy mechaniczne i ocena kompletności.
11. Delivery: ZIP i manifest.

### Adaptery
Każdy ciężki etap jest adapterem z jednym interfejsem `run(project, context) -> StageResult`. MVP zawiera adapter deterministyczny/demo, który produkuje kompletną paczkę bez płatnych API, oraz miejsce na adapter Hermes/LLM dla produkcji właściwej. Dzięki temu panel i orkiestrator można testować E2E bez kosztów.

### Skład
- PDF: Typst, jeśli dostępny; awaryjnie prosty generator HTML/print.
- EPUB: standardowa struktura EPUB 3, ZIP z poprawnym `mimetype`, OPF, nav i XHTML; walidacja strukturalna w testach, EPUBCheck jeśli dostępny.
- Okładka: grafika bez tekstu + deterministyczna typografia; MVP ma bezpieczny generator SVG/PNG bez zewnętrznego API.
- Landing page: samodzielny responsywny HTML/CSS/JS z metadanymi, OG i klauzulą AI.

## Model danych

### Project
`id`, `slug`, `title`, `topic`, `mode`, `language`, `audience`, `brand`, `tone`, `status`, `progress`, `created_at`, `updated_at`, `error`.

### Stage
`id`, `project_id`, `name`, `position`, `status`, `attempts`, `started_at`, `finished_at`, `message`, `artifact_paths`.

### Event
`id`, `project_id`, `timestamp`, `level`, `message`.

## Katalog projektu
```text
projects/<slug>/
├── project.json
├── research/
├── outline/
├── chapters/
├── images/
├── builds/
├── marketing/
├── qa/
└── delivery/
```

## Kontrola jakości
- etap przechodzi tylko po spełnieniu kryteriów,
- maksymalnie trzy automatyczne próby etapu,
- po trzeciej porażce projekt ma status `failed` z czytelnym błędem,
- PDF: istnieje, ma strony i tekst,
- EPUB: poprawna struktura ZIP i wymagane pliki,
- landing: meta viewport, CTA, brak poziomego overflow,
- delivery: wszystkie wymagane pliki plus sumy SHA-256,
- treść: minimalna liczba rozdziałów dla trybu, brak pustych sekcji i oznaczeń roboczych.

## API
- `POST /api/projects` — utworzenie projektu.
- `GET /api/projects` — lista.
- `GET /api/projects/{id}` — szczegóły i etapy.
- `POST /api/projects/{id}/start` — start.
- `POST /api/projects/{id}/pause` — pauza po bieżącym etapie.
- `POST /api/projects/{id}/resume` — wznowienie.
- `POST /api/projects/{id}/cancel` — anulowanie.
- `GET /api/projects/{id}/events` — log.
- `GET /api/projects/{id}/download` — ZIP paczki.
- `GET /health` — stan usługi.

## Błędy i odporność
- operacje idempotentne: ukończony etap nie uruchamia się ponownie bez resetu,
- atomowy zapis statusu po etapie,
- ścieżki ograniczone do katalogu projektów,
- nazwy plików i slug sanityzowane,
- brak sekretów w repo i artefaktach,
- restart procesu nie gubi projektu ani etapów.

## Bezpieczeństwo MVP
Panel jest prywatny. Wersja publiczna wymaga hasła lub Cloudflare Access. API nie przyjmuje dowolnych ścieżek ani poleceń. Uploady w MVP są ograniczone rozmiarem i rozszerzeniem.

## Wdrożenie
Aplikacja będzie uruchamiana jako jeden serwis FastAPI. Statyczny panel jest serwowany przez ten sam proces. Pierwsze wdrożenie może działać na obecnej maszynie przez publiczny Cloudflare Quick Tunnel; stały hosting backendu wymaga docelowego hosta z trwałym procesem. Statyczna strona informacyjna może trafić na Cloudflare Pages, ale produkcja książek nie może działać wyłącznie na Pages.

## Testy akceptacyjne
1. Utworzenie projektu każdego z trzech trybów.
2. Uruchomienie pełnego przebiegu demo od formularza do `completed`.
3. Po odświeżeniu panel pokazuje zapisany stan.
4. ZIP zawiera PDF, EPUB, okładkę, landing, copy, reklamy, QA i manifest.
5. Pauza/wznowienie i błąd etapu nie niszczą danych.
6. Panel działa przy szerokościach 390, 768, 1150 i 1440 px.
7. Live URL odpowiada, API health zwraca `ok`, a przebieg E2E działa w prawdziwej przeglądarce.

## Poza zakresem MVP
- automatyczne publikowanie w sklepie,
- płatności i konta klientów,
- marketplace szablonów,
- wieloużytkownikowy SaaS,
- automatyczny KDP upload,
- audiobook.
