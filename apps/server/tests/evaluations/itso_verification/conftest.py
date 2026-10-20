"""Deny accidental live DNS/sockets in this synthetic-only tool suite."""

import socket

import pytest


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError(
            "live networking forbidden in synthetic verification tests"
        )

    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
