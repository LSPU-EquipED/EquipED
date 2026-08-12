"""Fail-closed locality checks for model endpoints."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def is_private_endpoint(url: str) -> tuple[bool, str]:
    try:
        p = urlparse(url)
        if p.scheme not in {"http", "https"}:
            return False, "unsupported scheme"
        if p.username or p.password:
            return False, "credential-bearing URL"
        if p.query:
            return False, "query is not allowed"
        if p.fragment:
            return False, "fragment is not allowed"
        host = p.hostname
        if not host:
            return False, "missing hostname"
        if host.lower() in {
            "localhost",
            "localhost.localdomain",
            "host.docker.internal",
            "docker.host.internal",
            "gateway.docker.internal",
        }:
            return True, ""
        infos = socket.getaddrinfo(host, p.port, type=socket.SOCK_STREAM)
        if not infos:
            return False, "no addresses"
        for info in infos:
            addr = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
            if not (addr.is_private or addr.is_loopback or addr.is_link_local):
                return False, "public address"
        return True, ""
    except Exception:
        return False, "endpoint resolution failed"
