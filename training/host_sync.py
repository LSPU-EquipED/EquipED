#!/usr/bin/env python3
"""EquipED host sync: pull finished fine-tuned models onto the model server.

Run on the computer that runs the model server (Windows, llama.cpp). It asks
EquipED which GGUF files exist, downloads missing or changed ones into the
adapters folder, checks each against the SHA-256 EquipED recorded, rewrites
lora-flags.txt, and says what is new. It never restarts the server, never
deletes files, and never publishes. Standard library only.

    python host_sync.py --config host_sync.ini
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_API = "/api/v1/admin/training-data/host"
_SAFE_NAME = re.compile(r"^[a-z0-9]+-v[0-9]+\.gguf$")
_CHUNK = 1024 * 1024
_MAX_BYTES = 2 * 1024**3
_TIMEOUT = 60


class SyncError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    server_url: str
    key: str
    adapters_dir: Path
    flags_file: Path
    log_file: Path
    keep_latest: int = 2
    notify: bool = True


@dataclass
class SyncResult:
    downloaded: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    flags_changed: bool = False


def load_config(path: Path) -> Config:
    parser = configparser.ConfigParser()
    if not parser.read(path, encoding="utf-8"):
        raise SyncError(f"config file not found: {path}")
    try:
        section = parser["host_sync"]
        adapters_dir = Path(section["adapters_dir"])
        return Config(
            server_url=section["server_url"].rstrip("/"),
            key=section["key"],
            adapters_dir=adapters_dir,
            flags_file=Path(
                section.get("flags_file", str(adapters_dir / "lora-flags.txt"))
            ),
            log_file=Path(
                section.get("log_file", str(Path(path).parent / "host_sync.log"))
            ),
            keep_latest=section.getint("keep_latest", 2),
            notify=section.getboolean("notify", True),
        )
    except (KeyError, ValueError) as exc:
        raise SyncError(f"missing or invalid setting in {path}: {exc}") from exc


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so the host key is never sent to another address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SyncError(
            f"EquipED answered with a redirect (HTTP {code}); refusing to follow it "
            "so the key is not sent elsewhere. Check server_url in the config"
        )


_OPENER = urllib.request.build_opener(_NoRedirect)


def _open(config: Config, path: str):
    request = urllib.request.Request(
        config.server_url + _API + path, headers={"X-Host-Sync-Key": config.key}
    )
    return _OPENER.open(request, timeout=_TIMEOUT)


def _fetch_manifest(config: Config) -> list[dict]:
    try:
        with _open(config, "/manifest") as response:
            return json.loads(response.read().decode("utf-8"))["adapters"]
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise SyncError(
                "EquipED rejected the host key (revoked or wrong key)"
            ) from exc
        raise SyncError(f"EquipED returned HTTP {exc.code} for the manifest") from exc
    except (
        urllib.error.URLError,
        http.client.HTTPException,
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        raise SyncError(f"could not read the manifest from EquipED: {exc}") from exc


def _valid(entry: object) -> bool:
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("filename"), str)
        and _SAFE_NAME.match(entry["filename"]) is not None
        and isinstance(entry.get("sha256"), str)
        and isinstance(entry.get("size_bytes"), int)
        and not isinstance(entry["size_bytes"], bool)
        and 0 < entry["size_bytes"] <= _MAX_BYTES
        and isinstance(entry.get("adapter_id"), str)
        and isinstance(entry.get("agent_id"), str)
        and isinstance(entry.get("version"), int)
    )


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _up_to_date(target: Path, entry: dict) -> bool:
    return (
        target.is_file()
        and target.stat().st_size == entry["size_bytes"]
        and _sha256_of(target) == entry["sha256"]
    )


def _download(config: Config, entry: dict, target: Path) -> None:
    part = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    received = 0
    try:
        with (
            _open(config, f"/gguf/{entry['adapter_id']}") as response,
            open(part, "wb") as out,
        ):
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                received += len(chunk)
                if received > entry["size_bytes"]:
                    raise SyncError(
                        f"{entry['filename']}: larger than announced; discarded"
                    )
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != entry["sha256"]:
            raise SyncError(f"{entry['filename']}: checksum does not match; discarded")
        os.replace(part, target)
    except SyncError:
        part.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        part.unlink(missing_ok=True)
        raise SyncError(f"{entry['filename']}: download failed ({exc})") from exc


def select_loaded(entries: list[dict], keep_latest: int) -> list[dict]:
    """Latest keep_latest versions per agent, plus every published version."""
    by_agent: dict[str, list[dict]] = {}
    for entry in entries:
        by_agent.setdefault(entry["agent_id"], []).append(entry)
    chosen: list[dict] = []
    for agent in sorted(by_agent):
        ordered = sorted(by_agent[agent], key=lambda e: e["version"])
        newest = ordered[-keep_latest:] if keep_latest > 0 else []
        keep = {e["adapter_id"] for e in newest}
        keep |= {e["adapter_id"] for e in ordered if e.get("published")}
        chosen.extend(e for e in ordered if e["adapter_id"] in keep)
    return chosen


def _write_flags(config: Config, entries: list[dict]) -> bool:
    lines = [
        f'--lora-scaled "{config.adapters_dir / e["filename"]}:0.0"' for e in entries
    ]
    text = "\n".join(lines) + ("\n" if lines else "")
    old = (
        config.flags_file.read_text(encoding="utf-8")
        if config.flags_file.exists()
        else None
    )
    if old == text:
        return False
    config.flags_file.parent.mkdir(parents=True, exist_ok=True)
    temp = config.flags_file.with_name(config.flags_file.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, config.flags_file)
    return True


def _log(config: Config, message: str) -> None:
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config.log_file, "a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")


def notify_desktop(title: str, message: str) -> None:
    """Best-effort Windows balloon notification (needs a logged-in desktop)."""

    def quote(value: str) -> str:
        return value.replace("'", "''")

    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; "
        f"$n.ShowBalloonTip(10000, '{quote(title)}', '{quote(message)}', 'Info'); "
        "Start-Sleep -Seconds 12; $n.Dispose()"
    )
    subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def sync(
    config: Config, *, notify: Callable[[str, str], None] = notify_desktop
) -> SyncResult:
    result = SyncResult()
    try:
        manifest = _fetch_manifest(config)
    except SyncError as exc:
        result.errors.append(str(exc))
        _log(config, f"ERROR {exc}")
        return result

    config.adapters_dir.mkdir(parents=True, exist_ok=True)
    available: list[dict] = []
    for entry in manifest:
        if not _valid(entry):
            result.errors.append(f"ignored an unsafe or malformed entry: {entry!r}")
            continue
        target = config.adapters_dir / entry["filename"]
        try:
            if not _up_to_date(target, entry):
                _download(config, entry, target)
                result.downloaded.append(entry["filename"])
            available.append(entry)
        except (SyncError, OSError) as exc:
            result.errors.append(str(exc))

    try:
        result.flags_changed = _write_flags(
            config, select_loaded(available, config.keep_latest)
        )
    except OSError as exc:
        result.errors.append(f"could not write the flags file: {exc}")

    for error in result.errors:
        _log(config, f"ERROR {error}")
    if result.downloaded:
        names = ", ".join(n.removesuffix(".gguf") for n in result.downloaded)
        message = f"New model {names} ready, restart the model server to load it"
        _log(config, message)
        print(message)
        if config.notify:
            try:
                notify("EquipED: new fine-tuned model", message)
            except Exception as exc:  # a missing desktop must never break the sync
                _log(config, f"notification failed: {exc}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pull new EquipED models to this host."
    )
    parser.add_argument("--config", default="host_sync.ini")
    args = parser.parse_args(argv)
    try:
        config = load_config(Path(args.config))
    except SyncError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    result = sync(config)
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
