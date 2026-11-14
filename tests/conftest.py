"""Default tests must not resolve hosts or open HTTP connections."""

import os
import socket
import threading

import pytest


@pytest.fixture(autouse=True)
def offline_network_guard(monkeypatch, request):
    # Preserve the existing, explicit opt-in for these two public funding tests only.
    path = request.node.path
    if (path.name == "test_live_funding_sources.py" and path.parent.name == "integration"
            and os.environ.get("HANKELUOTSI_LIVE_FUNDING") == "1"):
        return

    def denied(*args, **kwargs):
        raise AssertionError("Network disabled in offline tests; use an isolated mock transport")

    pair_context = threading.local()
    real_pair = socket.socketpair
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def local_pair(*args, **kwargs):
        # Windows asyncio needs its stdlib socketpair loopback wakeup channel.
        previous = getattr(pair_context, "active", False)
        pair_context.active = True
        try:
            return real_pair(*args, **kwargs)
        finally:
            pair_context.active = previous

    def connection_allowed(address):
        return (getattr(pair_context, "active", False) and isinstance(address, tuple)
                and address[0] in ("127.0.0.1", "::1"))

    def guarded_connect(sock, address):
        if connection_allowed(address):
            return real_connect(sock, address)
        return denied()

    def guarded_connect_ex(sock, address):
        if connection_allowed(address):
            return real_connect_ex(sock, address)
        return denied()

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "socketpair", local_pair)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", denied)
