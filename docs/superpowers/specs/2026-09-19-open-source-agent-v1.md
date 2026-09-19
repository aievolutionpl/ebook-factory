# Ebook Factory Open-Source Agent v1 — Design Specification

## Goal
Turn Ebook Factory into a public AGPL-3.0 local-first application whose production pipeline can be operated by either Codex CLI or Claude Code, while preserving the deterministic demo provider and existing API compatibility.

## Product contract
- Users bring their own authenticated Codex CLI or Claude Code installation; Ebook Factory never stores provider credentials.
- `demo` remains the default provider so installation and tests work without paid services.
- `codex-cli` and `claude-code` are explicit opt-in providers selected per project.
- One provider protocol isolates the pipeline from command-specific details and leaves room for later API/Ollama adapters.
- Agent processes run non-interactively, inside the project's own workspace, with bounded timeout and captured logs.
- No shell interpolation: commands are argument arrays, not `shell=True` strings.

## Provider interface
Create `ebook_factory.providers` with:
- `AgentRequest(stage, prompt, workspace, output_file, timeout_seconds)`.
- `AgentResult(success, message, output_text, command, exit_code)`.
- `AgentProvider` protocol exposing `name`, `available()`, and `run(request)`.
- `DemoProvider`, `CodexCLIProvider`, `ClaudeCodeProvider`.
- Registry helpers `get_provider(name)` and `provider_statuses()`.

Availability uses `shutil.which`. CLI executable names default to `codex` and `claude`, overrideable by environment variables. Subprocesses receive a minimal inherited environment, use the project workspace as cwd, capture stdout/stderr, and time out. The output file must stay inside the workspace.

## Pipeline integration
- Add `provider` to project creation/model/persistence/API, default `demo`; allow only `demo`, `codex-cli`, `claude-code`.
- Existing projects/migrations remain readable and default to `demo`.
- Agent providers may generate stage text files but existing deterministic artifact packaging remains the final delivery mechanism.
- Each stage gets a bounded Polish prompt assembled from project metadata, source material and the expected output contract.
- Provider unavailability is a clear preflight failure before stage execution.
- Event log records provider and stage without leaking prompts, credentials or full source material.

## API and UI
- `GET /api/providers` returns provider name, label and availability.
- New-project wizard exposes provider selection and local setup guidance.
- Project detail displays the selected agent and its availability.
- Polish UI copy; internal stage identifiers never appear as user-facing labels.
- Premium calm Codex polish: 280px rail and 300px inspector desktop, center dominant; tablet uses a project drawer; one primary CTA; no content-obscuring toolbar; fewer borders/badges; completion summary; subtle scrollbars; responsive at 1440/1150/768/390/360; targets >=44px; no horizontal overflow.
- Preserve keyboard palette, drawer, inspector sheet, uploads and all current actions.

## Open-source release
- License: AGPL-3.0-only.
- Public repository: `aievolutionpl/ebook-factory` unless occupied; existing git history may be pushed.
- Include README with screenshots, architecture, quick start, provider setup, workflow, security/privacy notes, roadmap and AI disclosure.
- Include `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.env.example`, issue/PR templates and GitHub Actions.
- Documentation must state Codex CLI and Claude Code are third-party tools and users are responsible for their own subscriptions/logins.

## Quality gates
- Strict TDD for provider, persistence, API and UI contracts with captured RED then GREEN evidence.
- Full pytest suite pass.
- Node syntax pass and Impeccable detect zero blockers.
- Real-browser E2E for empty and populated states at canonical viewports.
- Fake CLI executables prove command invocation, cwd, output capture, timeout and failure behavior without using paid services.
- No secrets, generated ebooks, databases, venvs or local credentials committed.
