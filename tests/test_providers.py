import os
import stat
import time
from pathlib import Path

import pytest

from ebook_factory.providers import (
    AgentRequest,
    ClaudeCodeProvider,
    CodexCLIProvider,
    DemoProvider,
    get_provider,
    provider_statuses,
)


def make_fake_executable(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def make_request(workspace: Path, **overrides) -> AgentRequest:
    data = {
        "stage": "strategy",
        "prompt": "Napisz spokojna strategia",
        "workspace": workspace,
        "output_file": workspace / "agent-output.md",
        "timeout_seconds": 5,
    }
    data.update(overrides)
    return AgentRequest(**data)


def test_demo_provider_is_available_and_writes_bounded_output(tmp_path):
    provider = DemoProvider()
    request = make_request(tmp_path, prompt="x" * 20_000)

    result = provider.run(request)

    assert provider.available()
    assert result.success is True
    assert result.command == ["demo"]
    assert result.exit_code == 0
    assert request.output_file.read_text(encoding="utf-8").startswith("# Agent demo")
    assert len(result.output_text) < 5000


def test_cli_provider_availability_uses_env_override(monkeypatch, tmp_path):
    fake = make_fake_executable(
        tmp_path / "codex-fake",
        "import sys\nprint('ok')\nsys.exit(0)\n",
    )
    monkeypatch.setenv("EBOOK_FACTORY_CODEX_CLI", str(fake))

    assert CodexCLIProvider().available()


def test_cli_provider_invokes_argv_in_project_workspace_and_captures_output(
    monkeypatch, tmp_path
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    log_path = tmp_path / "argv.log"
    fake = make_fake_executable(
        tmp_path / "codex-fake",
        """
import os
import pathlib
import sys

log = pathlib.Path(os.environ["FAKE_LOG"])
log.write_text("\\n".join([os.getcwd(), *sys.argv[1:]]), encoding="utf-8")
print("stdout marker")
print("stderr marker", file=sys.stderr)
pathlib.Path("relative-proof.txt").write_text("cwd ok", encoding="utf-8")
sys.exit(0)
""",
    )
    monkeypatch.setenv("EBOOK_FACTORY_CODEX_CLI", str(fake))
    monkeypatch.setenv("FAKE_LOG", str(log_path))

    result = CodexCLIProvider().run(make_request(workspace))

    assert result.success is True
    assert result.command[0] == str(fake)
    assert result.command[1:3] == ["exec", "--skip-git-repo-check"]
    assert "--output-last-message" in result.command
    assert result.command[-1] == "-"
    assert "stdout marker" in result.message
    assert "stderr marker" in result.message
    assert (workspace / "relative-proof.txt").read_text(encoding="utf-8") == "cwd ok"
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines[0] == str(workspace)
    assert any(line == str(workspace / "agent-output.md") for line in log_lines)


def test_claude_provider_uses_real_noninteractive_cli_and_persists_stdout(monkeypatch, tmp_path):
    fake = make_fake_executable(
        tmp_path / "claude-fake",
        "import sys\nprint('chapter from claude')\nsys.exit(0)\n",
    )
    monkeypatch.setenv("EBOOK_FACTORY_CLAUDE_CODE", str(fake))
    request = make_request(tmp_path)

    result = ClaudeCodeProvider().run(request)

    assert result.success is True
    assert result.command[1:] == [
        "--print",
        "--output-format",
        "text",
        "--permission-mode",
        "dontAsk",
        "--safe-mode",
        "--tools",
        "",
    ]
    assert request.output_file.read_text(encoding="utf-8").strip() == "chapter from claude"
    assert result.output_text.strip() == "chapter from claude"


def test_cli_provider_fails_when_output_file_escapes_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    request = make_request(workspace, output_file=tmp_path / "outside.md")

    result = DemoProvider().run(request)

    assert result.success is False
    assert "inside the workspace" in result.message


def test_cli_provider_reports_nonzero_exit(monkeypatch, tmp_path):
    fake = make_fake_executable(
        tmp_path / "claude-fake",
        """
import sys
print("bad stdout")
print("bad stderr", file=sys.stderr)
sys.exit(7)
""",
    )
    monkeypatch.setenv("EBOOK_FACTORY_CLAUDE_CODE", str(fake))

    result = ClaudeCodeProvider().run(make_request(tmp_path))

    assert result.success is False
    assert result.exit_code == 7
    assert "bad stdout" in result.message
    assert "bad stderr" in result.message


def test_cli_provider_times_out_and_returns_bounded_message(monkeypatch, tmp_path):
    fake = make_fake_executable(
        tmp_path / "codex-slow",
        """
import time
print("starting slow command")
time.sleep(5)
""",
    )
    monkeypatch.setenv("EBOOK_FACTORY_CODEX_CLI", str(fake))
    request = make_request(tmp_path, timeout_seconds=1)

    started = time.monotonic()
    result = CodexCLIProvider().run(request)

    assert time.monotonic() - started < 4
    assert result.success is False
    assert result.exit_code is None
    assert "timed out" in result.message.lower()
    assert len(result.message) < 5000


def test_provider_registry_statuses_include_public_labels(monkeypatch, tmp_path):
    fake = make_fake_executable(tmp_path / "codex", "print('ok')\n")
    monkeypatch.setenv("EBOOK_FACTORY_CODEX_CLI", str(fake))
    statuses = provider_statuses()

    by_name = {status["name"]: status for status in statuses}
    assert set(by_name) == {"demo", "codex-cli", "claude-code"}
    assert by_name["demo"]["available"] is True
    assert by_name["codex-cli"]["label"] == "Codex CLI"
    assert by_name["claude-code"]["label"] == "Claude Code"
    assert get_provider("demo").name == "demo"
    with pytest.raises(ValueError):
        get_provider("unknown")


def test_no_provider_module_uses_shell_true():
    provider_source = Path("src/ebook_factory/providers.py").read_text(encoding="utf-8")
    assert "shell=True" not in provider_source
