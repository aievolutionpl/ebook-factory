import base64
import os
import re
import socket
import stat
import subprocess
import time
import urllib.error
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

# Minimal PATH that excludes any real, installed `cloudflared` on this
# machine (e.g. /home/aibot/bin), used to prove the "fail cleanly" and
# "prefer $HOME/bin" behaviors without depending on host binaries.
MINIMAL_SYSTEM_PATH = "/usr/bin:/bin"

AUTH_ENV = {
    "EBOOK_FACTORY_AUTH_USER": "testuser",
    "EBOOK_FACTORY_AUTH_PASSWORD": "testpass123",
}


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


def _basic_header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _stop(pid: int) -> None:
    os.kill(pid, 15)
    deadline = time.time() + 10
    while time.time() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(0.2)


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


def test_cloudflared_tunnel_script_never_downloads_a_binary():
    text = TUNNEL_SCRIPT.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "curl" not in lowered
    assert "wget" not in lowered
    assert "download" not in lowered


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
        env=dict(os.environ, **AUTH_ENV),
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
        _stop(pid)


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
        env=dict(os.environ, **AUTH_ENV),
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
            env=dict(os.environ, **AUTH_ENV),
        )
        assert second.returncode != 0
        assert "already running" in second.stderr.lower()
    finally:
        _stop(pid)


def test_start_production_refuses_to_start_without_credentials_or_flag(tmp_path):
    host = "127.0.0.1"
    port = _free_port()
    data_dir = tmp_path / "data"
    log_dir = tmp_path / "logs"

    env = dict(os.environ)
    env.pop("EBOOK_FACTORY_AUTH_USER", None)
    env.pop("EBOOK_FACTORY_AUTH_PASSWORD", None)

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
        env=env,
    )

    assert result.returncode != 0
    assert "credential" in result.stderr.lower() or "auth" in result.stderr.lower()
    assert not (log_dir / "server.pid").is_file()


def test_start_production_allows_explicit_opt_out_without_credentials(tmp_path):
    host = "127.0.0.1"
    port = _free_port()
    data_dir = tmp_path / "data"
    log_dir = tmp_path / "logs"

    env = dict(os.environ)
    env.pop("EBOOK_FACTORY_AUTH_USER", None)
    env.pop("EBOOK_FACTORY_AUTH_PASSWORD", None)

    result = subprocess.run(
        [
            str(START_SCRIPT),
            "--host", host,
            "--port", str(port),
            "--data-dir", str(data_dir),
            "--log-dir", str(log_dir),
            "--allow-no-auth",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    pid_file = log_dir / "server.pid"
    pid = int(pid_file.read_text().strip())
    try:
        _wait_for_health(host, port)
        with urllib.request.urlopen(f"http://{host}:{port}/api/projects", timeout=5) as resp:
            assert resp.status == 200
    finally:
        _stop(pid)


def test_start_production_with_credentials_enforces_http_basic_auth(tmp_path):
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
        env=dict(os.environ, **AUTH_ENV),
    )
    assert result.returncode == 0, result.stderr
    pid_file = log_dir / "server.pid"
    pid = int(pid_file.read_text().strip())

    try:
        _wait_for_health(host, port)

        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=5) as resp:
            assert resp.status == 200

        try:
            urllib.request.urlopen(f"http://{host}:{port}/api/projects", timeout=5)
            assert False, "expected 401 without credentials"
        except urllib.error.HTTPError as exc:
            assert exc.code == 401

        request = urllib.request.Request(
            f"http://{host}:{port}/api/projects",
            headers={
                "Authorization": _basic_header(
                    AUTH_ENV["EBOOK_FACTORY_AUTH_USER"], AUTH_ENV["EBOOK_FACTORY_AUTH_PASSWORD"]
                )
            },
        )
        with urllib.request.urlopen(request, timeout=5) as resp:
            assert resp.status == 200
    finally:
        _stop(pid)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def test_cloudflared_tunnel_prefers_installed_home_bin_binary(tmp_path):
    fake_home = tmp_path / "home"
    fake_home_bin = fake_home / "bin"
    fake_home_bin.mkdir(parents=True)
    fake_cloudflared = fake_home_bin / "cloudflared"
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
    env["HOME"] = str(fake_home)
    env["PATH"] = MINIMAL_SYSTEM_PATH

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


def test_cloudflared_tunnel_falls_back_to_path_when_home_bin_missing(tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_bin_dir = tmp_path / "fakebin"
    fake_bin_dir.mkdir()
    fake_cloudflared = fake_bin_dir / "cloudflared"
    fake_cloudflared.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'INF |  https://fake-path-tunnel.trycloudflare.com  |'\n"
        "sleep 30\n"
    )
    fake_cloudflared.chmod(0o755)

    log_dir = tmp_path / "logs"
    env = dict(os.environ)
    env["HOME"] = str(fake_home)
    env["PATH"] = f"{fake_bin_dir}:{MINIMAL_SYSTEM_PATH}"

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
        assert "https://fake-path-tunnel.trycloudflare.com" in result.stdout
    finally:
        if pid_file.is_file():
            pid = int(pid_file.read_text().strip())
            if _pid_alive(pid):
                os.kill(pid, 15)


def test_cloudflared_tunnel_fails_cleanly_when_binary_missing(tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    log_dir = tmp_path / "logs"
    env = dict(os.environ)
    env["HOME"] = str(fake_home)
    env["PATH"] = MINIMAL_SYSTEM_PATH

    result = subprocess.run(
        [
            str(TUNNEL_SCRIPT),
            "--port", "8765",
            "--log-dir", str(log_dir),
            "--wait-seconds", "5",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert result.returncode != 0
    assert "cloudflared" in result.stderr.lower()
    assert "not found" in result.stderr.lower()
    assert not (log_dir / "cloudflared.pid").is_file()
