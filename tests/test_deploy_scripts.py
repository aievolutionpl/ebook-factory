import os
import re
import socket
import stat
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy"
START_SCRIPT = DEPLOY_DIR / "start-production.sh"
TUNNEL_SCRIPT = DEPLOY_DIR / "cloudflared-tunnel.sh"

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"TUNNEL_TOKEN\s*=\s*['\"]?[A-Za-z0-9._-]{10,}"),
    re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._-]{10,}"),
]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(host: str, port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except OSError as exc:
            last_error = exc
        time.sleep(0.5)
    raise AssertionError(f"server never became healthy: {last_error}")


@pytest.mark.parametrize("script", [START_SCRIPT, TUNNEL_SCRIPT])
def test_deploy_script_exists_and_is_executable(script: Path):
    assert script.is_file(), f"{script} does not exist"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR, f"{script} is not executable"


@pytest.mark.parametrize("script", [START_SCRIPT, TUNNEL_SCRIPT])
def test_deploy_script_uses_strict_shell_flags(script: Path):
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash") or text.startswith("#!/bin/bash")
    assert "set -euo pipefail" in text


@pytest.mark.parametrize("script", [START_SCRIPT, TUNNEL_SCRIPT])
def test_deploy_script_has_no_embedded_secrets(script: Path):
    text = script.read_text(encoding="utf-8")
    for pattern in SECRET_PATTERNS:
        assert not pattern.search(text), f"possible embedded secret in {script}: {pattern.pattern}"


def test_start_production_binds_configurable_host_port_and_data_dir(tmp_path):
    host = "127.0.0.1"
    port = _free_port()
    data_dir = tmp_path / "data"
    log_dir = tmp_path / "logs"

    result = subprocess.run(
        [
            str(START_SCRIPT),
            "--host", host,
            "--port", str(port),
            "--data-dir", str(data_dir),
            "--log-dir", str(log_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr

    pid_file = log_dir / "server.pid"
    log_file = log_dir / "server.log"
    assert pid_file.is_file()
    assert log_file.is_file()
    pid = int(pid_file.read_text().strip())

    try:
        _wait_for_health(host, port)
        assert data_dir.is_dir()
        assert (data_dir / "factory.db").is_file()
    finally:
        os.kill(pid, 15)
        deadline = time.time() + 10
        while time.time() < deadline:
            if not _pid_alive(pid):
                break
            time.sleep(0.2)


def test_start_production_refuses_duplicate_start(tmp_path):
    host = "127.0.0.1"
    port = _free_port()
    data_dir = tmp_path / "data"
    log_dir = tmp_path / "logs"

    first = subprocess.run(
        [
            str(START_SCRIPT),
            "--host", host,
            "--port", str(port),
            "--data-dir", str(data_dir),
            "--log-dir", str(log_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert first.returncode == 0, first.stderr
    pid_file = log_dir / "server.pid"
    pid = int(pid_file.read_text().strip())

    try:
        _wait_for_health(host, port)
        second = subprocess.run(
            [
                str(START_SCRIPT),
                "--host", host,
                "--port", str(_free_port()),
                "--data-dir", str(data_dir),
                "--log-dir", str(log_dir),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert second.returncode != 0
        assert "already running" in second.stderr.lower()
    finally:
        os.kill(pid, 15)
        deadline = time.time() + 10
        while time.time() < deadline:
            if not _pid_alive(pid):
                break
            time.sleep(0.2)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_cloudflared_tunnel_uses_local_binary_and_reports_public_url(tmp_path):
    fake_bin_dir = tmp_path / "fakebin"
    fake_bin_dir.mkdir()
    fake_cloudflared = fake_bin_dir / "cloudflared"
    fake_cloudflared.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'INF Thank you for trying Cloudflare Tunnel.'\n"
        "echo 'INF +--------------------------------------------------------------------------------------+'\n"
        "echo 'INF |  https://fake-tunnel-name.trycloudflare.com                                          |'\n"
        "echo 'INF +--------------------------------------------------------------------------------------+'\n"
        "sleep 30\n"
    )
    fake_cloudflared.chmod(0o755)

    log_dir = tmp_path / "logs"
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin_dir}:{env['PATH']}"

    result = subprocess.run(
        [
            str(TUNNEL_SCRIPT),
            "--port", "8765",
            "--log-dir", str(log_dir),
            "--wait-seconds", "15",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    pid_file = log_dir / "cloudflared.pid"
    try:
        assert result.returncode == 0, result.stderr
        assert "https://fake-tunnel-name.trycloudflare.com" in result.stdout
        assert pid_file.is_file()
    finally:
        if pid_file.is_file():
            pid = int(pid_file.read_text().strip())
            if _pid_alive(pid):
                os.kill(pid, 15)
