"""Tests for training/host_sync.py against a fake local server."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "host_sync.py"
spec = importlib.util.spec_from_file_location("host_sync", SCRIPT)
host_sync = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = host_sync  # dataclasses look the module up by name
spec.loader.exec_module(host_sync)

KEY = "hsk_test"


def _entry(agent, version, payload, *, published=False, filename=None, adapter_id=None):
    return {
        "adapter_id": adapter_id or f"{agent}-{version}-id",
        "agent_id": agent,
        "version": version,
        "filename": filename or f"{agent}-v{version}.gguf",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "published": published,
    }


class _Server:
    """A fake EquipED serving a manifest and files."""

    def __init__(self, entries, files, *, corrupt=(), truncate=(), redirect_to=None):
        self.entries, self.files, self.corrupt = entries, files, set(corrupt)
        self.truncate, self.redirect_to = set(truncate), redirect_to
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                outer.requests.append((self.path, self.headers.get("X-Host-Sync-Key")))
                if outer.redirect_to:
                    self.send_response(301)
                    self.send_header("Location", outer.redirect_to + self.path)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if self.headers.get("X-Host-Sync-Key") != KEY:
                    self.send_error(404)
                    return
                if self.path.endswith("/host/manifest"):
                    body = json.dumps({"adapters": outer.entries}).encode()
                else:
                    adapter_id = self.path.rsplit("/", 1)[1]
                    body = outer.files[adapter_id]
                    if adapter_id in outer.truncate:
                        # chunked reply that drops before the terminating chunk
                        self.send_response(200)
                        self.send_header("Transfer-Encoding", "chunked")
                        self.end_headers()
                        half = body[: len(body) // 2]
                        self.wfile.write(f"{len(half):x}\r\n".encode() + half + b"\r\n")
                        self.wfile.flush()
                        self.close_connection = True
                        return
                    if adapter_id in outer.corrupt:
                        body = body[:-1] + b"X"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self.thread.start()
        self.closed = False

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


@pytest.fixture
def make_server():
    servers = []

    def make(entries, files, **kwargs):
        server = _Server(entries, files, **kwargs)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def _config(tmp_path, server, **overrides):
    values = dict(
        server_url=server.url,
        key=KEY,
        adapters_dir=tmp_path / "adapters",
        flags_file=tmp_path / "adapters" / "lora-flags.txt",
        log_file=tmp_path / "host_sync.log",
        keep_latest=2,
        notify=False,
    )
    values.update(overrides)
    return host_sync.Config(**values)


P3, P4, P5 = (b"GGUF" + bytes([n]) * 40 for n in (3, 4, 5))


def _three(make_server):
    entries = [_entry("sme", 3, P3), _entry("sme", 4, P4), _entry("sme", 5, P5)]
    files = {"sme-3-id": P3, "sme-4-id": P4, "sme-5-id": P5}
    return make_server(entries, files)


def test_downloads_new_files_and_writes_flags(tmp_path, make_server):
    server = _three(make_server)
    config = _config(tmp_path, server)

    result = host_sync.sync(config)

    assert sorted(result.downloaded) == ["sme-v3.gguf", "sme-v4.gguf", "sme-v5.gguf"]
    assert (config.adapters_dir / "sme-v5.gguf").read_bytes() == P5
    assert not list(config.adapters_dir.glob("*.part"))
    flags = config.flags_file.read_text(encoding="utf-8").splitlines()
    # keep_latest = 2 -> v4 and v5 only; v3 stays on disk but is not listed
    assert flags == [
        f'--lora-scaled "{config.adapters_dir / "sme-v4.gguf"}:0.0"',
        f'--lora-scaled "{config.adapters_dir / "sme-v5.gguf"}:0.0"',
    ]


def test_second_run_downloads_nothing_and_changes_nothing(tmp_path, make_server):
    server = _three(make_server)
    config = _config(tmp_path, server)
    host_sync.sync(config)
    before = config.flags_file.read_text(encoding="utf-8")
    server.requests.clear()

    result = host_sync.sync(config)

    assert result.downloaded == [] and result.flags_changed is False
    assert config.flags_file.read_text(encoding="utf-8") == before
    assert [p for p, _ in server.requests if "/host/gguf/" in p] == []


def test_checksum_mismatch_leaves_no_file_and_is_reported(tmp_path, make_server):
    entries = [_entry("sme", 3, P3)]
    server = make_server(entries, {"sme-3-id": P3}, corrupt={"sme-3-id"})
    config = _config(tmp_path, server)

    result = host_sync.sync(config)

    assert result.downloaded == []
    assert result.errors and "sme-v3.gguf" in result.errors[0]
    assert not (config.adapters_dir / "sme-v3.gguf").exists()
    assert not list(config.adapters_dir.glob("*.part"))


def test_a_corrupt_download_does_not_replace_an_existing_file(tmp_path, make_server):
    entries = [_entry("sme", 3, P3)]
    server = make_server(entries, {"sme-3-id": P3}, corrupt={"sme-3-id"})
    config = _config(tmp_path, server)
    config.adapters_dir.mkdir()
    (config.adapters_dir / "sme-v3.gguf").write_bytes(b"old content")

    result = host_sync.sync(config)

    assert result.errors
    assert (config.adapters_dir / "sme-v3.gguf").read_bytes() == b"old content"
    assert not list(config.adapters_dir.glob("*.part"))


def test_published_version_is_always_listed_even_if_old(tmp_path, make_server):
    entries = [
        _entry("sme", 1, P3, published=True, adapter_id="sme-1-id"),
        _entry("sme", 4, P4),
        _entry("sme", 5, P5),
    ]
    server = make_server(entries, {"sme-1-id": P3, "sme-4-id": P4, "sme-5-id": P5})
    config = _config(tmp_path, server)
    host_sync.sync(config)
    flags = "".join(config.flags_file.read_text(encoding="utf-8").splitlines())
    assert "sme-v1.gguf" in flags and "sme-v4.gguf" in flags and "sme-v5.gguf" in flags


def test_keep_latest_applies_per_agent(tmp_path, make_server):
    entries = [_entry("sme", 1, P3), _entry("gad", 1, P4)]
    server = make_server(entries, {"sme-1-id": P3, "gad-1-id": P4})
    config = _config(tmp_path, server, keep_latest=1)
    host_sync.sync(config)
    flags = "".join(config.flags_file.read_text(encoding="utf-8").splitlines())
    assert "sme-v1.gguf" in flags and "gad-v1.gguf" in flags


@pytest.mark.parametrize(
    "filename",
    [
        "..\\..\\evil.gguf",
        "../evil-v1.gguf",
        "sub/sme-v1.gguf",
        "SME-v1.gguf",
        "x.gguf",
    ],
)
def test_unsafe_filenames_are_rejected(tmp_path, make_server, filename):
    bad = _entry("sme", 3, P3, filename=filename)
    server = make_server([bad], {"sme-3-id": P3})
    config = _config(tmp_path, server)
    result = host_sync.sync(config)
    assert result.downloaded == [] and result.errors
    assert not [p for p, _ in server.requests if "/host/gguf/" in p]
    assert not (tmp_path / "evil.gguf").exists()
    assert not (tmp_path / "evil-v1.gguf").exists()


def test_oversized_entries_are_rejected_without_downloading(tmp_path, make_server):
    huge = _entry("sme", 3, P3)
    huge["size_bytes"] = 3 * 1024**3
    server = make_server([huge], {"sme-3-id": P3})
    config = _config(tmp_path, server)
    result = host_sync.sync(config)
    assert result.downloaded == [] and result.errors
    assert not [p for p, _ in server.requests if "/host/gguf/" in p]


def test_a_failed_file_does_not_stop_the_others(tmp_path, make_server):
    entries = [_entry("sme", 3, P3), _entry("sme", 4, P4)]
    server = make_server(
        entries, {"sme-3-id": P3, "sme-4-id": P4}, corrupt={"sme-3-id"}
    )
    config = _config(tmp_path, server)
    result = host_sync.sync(config)
    assert result.downloaded == ["sme-v4.gguf"]
    assert len(result.errors) == 1


def test_new_files_are_logged_and_notified_once(tmp_path, make_server):
    server = make_server([_entry("sme", 3, P3)], {"sme-3-id": P3})
    config = _config(tmp_path, server, notify=True)
    sent = []
    host_sync.sync(config, notify=lambda title, message: sent.append((title, message)))
    assert sent and "sme-v3" in sent[0][1]
    assert "restart the model server" in sent[0][1]
    assert "sme-v3" in config.log_file.read_text(encoding="utf-8")
    sent.clear()
    host_sync.sync(config, notify=lambda title, message: sent.append((title, message)))
    assert sent == []


def test_a_failing_notification_is_ignored(tmp_path, make_server):
    server = make_server([_entry("sme", 3, P3)], {"sme-3-id": P3})
    config = _config(tmp_path, server, notify=True)

    def boom(title, message):
        raise OSError("no desktop")

    result = host_sync.sync(config, notify=boom)
    assert result.downloaded == ["sme-v3.gguf"]


def test_wrong_key_is_a_clear_error_and_never_echoed(tmp_path, make_server):
    server = make_server([], {})
    config = _config(tmp_path, server, key="hsk_wrong")
    result = host_sync.sync(config)
    assert result.errors and "key" in result.errors[0].lower()
    logged = config.log_file.read_text(encoding="utf-8")
    assert "hsk_wrong" not in "".join(result.errors) + logged


def test_unreachable_server_is_a_clear_error(tmp_path, make_server):
    server = make_server([], {})
    config = _config(tmp_path, server)
    server.close()
    result = host_sync.sync(config)
    assert result.errors
    assert KEY not in "".join(result.errors)


def test_load_config_reads_the_ini_file(tmp_path):
    ini = tmp_path / "host_sync.ini"
    ini.write_text(
        "[host_sync]\nserver_url = https://app.example\nkey = hsk_x\n"
        f"adapters_dir = {tmp_path / 'adapters'}\nkeep_latest = 3\nnotify = false\n",
        encoding="utf-8",
    )
    config = host_sync.load_config(ini)
    assert config.server_url == "https://app.example"
    assert config.keep_latest == 3 and config.notify is False
    assert config.flags_file == tmp_path / "adapters" / "lora-flags.txt"


def test_main_returns_nonzero_when_something_failed(tmp_path, make_server):
    server = make_server([_entry("sme", 3, P3)], {"sme-3-id": P3}, corrupt={"sme-3-id"})
    ini = tmp_path / "host_sync.ini"
    ini.write_text(
        f"[host_sync]\nserver_url = {server.url}\nkey = {KEY}\n"
        f"adapters_dir = {tmp_path / 'adapters'}\nnotify = false\n",
        encoding="utf-8",
    )
    assert host_sync.main(["--config", str(ini)]) == 1


def test_main_returns_two_for_a_missing_config(tmp_path):
    assert host_sync.main(["--config", str(tmp_path / "missing.ini")]) == 2


def test_a_dropped_chunked_download_is_an_error_not_a_crash(tmp_path, make_server):
    entries = [_entry("sme", 3, P3), _entry("sme", 4, P4)]
    server = make_server(
        entries, {"sme-3-id": P3, "sme-4-id": P4}, truncate={"sme-3-id"}
    )
    config = _config(tmp_path, server)

    result = host_sync.sync(config)

    assert result.downloaded == ["sme-v4.gguf"]
    assert len(result.errors) == 1 and "sme-v3.gguf" in result.errors[0]
    assert not (config.adapters_dir / "sme-v3.gguf").exists()
    assert not list(config.adapters_dir.glob("*.part"))
    assert "sme-v3.gguf" in config.log_file.read_text(encoding="utf-8")


def test_main_returns_one_for_a_dropped_download(tmp_path, make_server):
    server = make_server(
        [_entry("sme", 3, P3)], {"sme-3-id": P3}, truncate={"sme-3-id"}
    )
    ini = tmp_path / "host_sync.ini"
    ini.write_text(
        f"[host_sync]\nserver_url = {server.url}\nkey = {KEY}\n"
        f"adapters_dir = {tmp_path / 'adapters'}\nnotify = false\n",
        encoding="utf-8",
    )
    assert host_sync.main(["--config", str(ini)]) == 1


def test_redirects_are_refused_and_the_key_is_not_sent_elsewhere(tmp_path, make_server):
    elsewhere = make_server([], {})
    server = make_server([], {}, redirect_to=elsewhere.url)
    config = _config(tmp_path, server)

    result = host_sync.sync(config)

    assert result.errors and "redirect" in result.errors[0].lower()
    assert KEY not in "".join(result.errors)
    assert elsewhere.requests == []


def test_a_percent_sign_in_a_setting_is_plain_text(tmp_path):
    ini = tmp_path / "host_sync.ini"
    ini.write_text(
        "[host_sync]\nserver_url = https://app.example\nkey = hsk_100%x\n"
        f"adapters_dir = {tmp_path / '100%models'}\n",
        encoding="utf-8",
    )
    config = host_sync.load_config(ini)
    assert config.key == "hsk_100%x"
    assert config.adapters_dir.name == "100%models"


def test_main_returns_two_for_a_malformed_config(tmp_path, capsys):
    ini = tmp_path / "host_sync.ini"
    ini.write_text("server_url = no section header\n", encoding="utf-8")
    assert host_sync.main(["--config", str(ini)]) == 2
    assert "Configuration error" in capsys.readouterr().err
