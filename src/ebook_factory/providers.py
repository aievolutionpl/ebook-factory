"""Agent provider adapters for local deterministic and CLI-backed runs."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

MAX_CAPTURE_CHARS = 4000


@dataclass(frozen=True)
class AgentRequest:
    stage: str
    prompt: str
    workspace: Path
    output_file: Path
    timeout_seconds: int


@dataclass(frozen=True)
class AgentResult:
    success: bool
    message: str
    output_text: str
    command: list[str]
    exit_code: int | None


class AgentProvider(Protocol):
    name: str
    label: str

    def available(self) -> bool:
        """Return whether this provider can run on this machine."""

    def run(self, request: AgentRequest) -> AgentResult:
        """Run a single bounded agent request."""


def _bounded(text: str, limit: int = MAX_CAPTURE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 40] + "\n...[truncated by Ebook Factory]..."


def _safe_output_path(request: AgentRequest) -> tuple[bool, str]:
    workspace = request.workspace.resolve()
    output_file = request.output_file.resolve()
    try:
        output_file.relative_to(workspace)
    except ValueError:
        return False, "agent output_file must stay inside the workspace"
    return True, ""


def _minimal_env() -> dict[str, str]:
    allowed_names = {
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "TMPDIR",
        "USER",
    }
    allowed_prefixes = ("EBOOK_FACTORY_", "FAKE_")
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in allowed_names or key.startswith(allowed_prefixes):
            env[key] = value
    return env


class DemoProvider:
    name = "demo"
    label = "Demo"

    def available(self) -> bool:
        return True

    def run(self, request: AgentRequest) -> AgentResult:
        ok, message = _safe_output_path(request)
        if not ok:
            return AgentResult(False, message, "", ["demo"], None)

        request.workspace.mkdir(parents=True, exist_ok=True)
        request.output_file.parent.mkdir(parents=True, exist_ok=True)
        output_text = (
            f"# Agent demo: {request.stage}\n\n"
            "Deterministyczny provider demo zachowuje lokalny przeplyw pracy. "
            "Zewnetrzny agent nie zostal uruchomiony.\n\n"
            "## Skrot promptu\n"
            f"{_bounded(request.prompt, 1200)}\n"
        )
        request.output_file.write_text(output_text, encoding="utf-8")
        return AgentResult(
            success=True,
            message=f"demo provider completed {request.stage}",
            output_text=_bounded(output_text),
            command=["demo"],
            exit_code=0,
        )


class _CLIProvider:
    name: str
    label: str
    executable_name: str
    env_var: str

    def _executable(self) -> str | None:
        configured = os.environ.get(self.env_var)
        if configured:
            path = Path(configured)
            return str(path) if path.is_file() and os.access(path, os.X_OK) else None
        return shutil.which(self.executable_name)

    def available(self) -> bool:
        return self._executable() is not None

    def _command(self, executable: str, request: AgentRequest) -> list[str]:
        return [
            executable,
            "--stage",
            request.stage,
            "--output",
            str(request.output_file.resolve()),
        ]

    def run(self, request: AgentRequest) -> AgentResult:
        ok, message = _safe_output_path(request)
        executable = self._executable()
        command = self._command(executable or self.executable_name, request)
        if not ok:
            return AgentResult(False, message, "", command, None)
        if executable is None:
            return AgentResult(
                False,
                f"{self.label} executable is not available",
                "",
                command,
                None,
            )

        request.workspace.mkdir(parents=True, exist_ok=True)
        request.output_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                self._command(executable, request),
                input=request.prompt,
                text=True,
                cwd=request.workspace,
                env=_minimal_env(),
                capture_output=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            captured = "\n".join(
                part
                for part in (
                    exc.stdout if isinstance(exc.stdout, str) else "",
                    exc.stderr if isinstance(exc.stderr, str) else "",
                )
                if part
            )
            return AgentResult(
                False,
                _bounded(f"{self.label} timed out after {request.timeout_seconds}s\n{captured}"),
                _bounded(captured),
                command,
                None,
            )

        captured = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        success = completed.returncode == 0
        if success and not request.output_file.is_file() and completed.stdout.strip():
            request.output_file.write_text(completed.stdout, encoding="utf-8")
        output_text = ""
        if request.output_file.is_file():
            output_text = _bounded(request.output_file.read_text(encoding="utf-8", errors="replace"))
        return AgentResult(
            success=success,
            message=_bounded(captured or f"{self.label} exited with code {completed.returncode}"),
            output_text=output_text,
            command=self._command(executable, request),
            exit_code=completed.returncode,
        )


class CodexCLIProvider(_CLIProvider):
    name = "codex-cli"
    label = "Codex CLI"
    executable_name = "codex"
    env_var = "EBOOK_FACTORY_CODEX_CLI"

    def _command(self, executable: str, request: AgentRequest) -> list[str]:
        return [
            executable,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--output-last-message",
            str(request.output_file.resolve()),
            "-",
        ]


class ClaudeCodeProvider(_CLIProvider):
    name = "claude-code"
    label = "Claude Code"
    executable_name = "claude"
    env_var = "EBOOK_FACTORY_CLAUDE_CODE"

    def _command(self, executable: str, request: AgentRequest) -> list[str]:
        return [
            executable,
            "--print",
            "--output-format",
            "text",
            "--permission-mode",
            "dontAsk",
            "--safe-mode",
            "--tools",
            "",
        ]


_PROVIDERS: dict[str, AgentProvider] = {
    "demo": DemoProvider(),
    "codex-cli": CodexCLIProvider(),
    "claude-code": ClaudeCodeProvider(),
}


def get_provider(name: str) -> AgentProvider:
    try:
        return _PROVIDERS[name]
    except KeyError as exc:
        raise ValueError(f"unknown provider {name!r}") from exc


def provider_statuses() -> list[dict[str, object]]:
    return [
        {
            "name": provider.name,
            "label": provider.label,
            "available": provider.available(),
        }
        for provider in _PROVIDERS.values()
    ]
