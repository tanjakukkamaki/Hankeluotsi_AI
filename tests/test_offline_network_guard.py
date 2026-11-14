"""A missing HTTP mock must fail before DNS or connection, even for direct IP URLs."""

import socket

import httpx2
import pytest


def test_default_guard_denies_dns_and_tcp_connection():
    for operation, arguments in ((socket.getaddrinfo, ("example.invalid", 443)),
                                 (socket.create_connection, (("198.51.100.1", 443),))):
        with pytest.raises(AssertionError, match="Network disabled"):
            operation(*arguments)


def test_real_http_backend_cannot_escape_offline_guard():
    with httpx2.Client(timeout=1, trust_env=False,
                       transport=httpx2.HTTPTransport(retries=0, trust_env=False)) as client:
        with pytest.raises(AssertionError, match="Network disabled"):
            client.get("https://198.51.100.1/models")


def test_direct_numeric_and_loopback_sockets_cannot_bypass_guard():
    with socket.socket() as sock:
        for operation, address in ((sock.connect, ("198.51.100.1", 443)),
                                   (sock.connect_ex, ("127.0.0.1", 1234))):
            with pytest.raises(AssertionError, match="Network disabled"):
                operation(address)
    with socket.socket(type=socket.SOCK_DGRAM) as sock:
        with pytest.raises(AssertionError, match="Network disabled"):
            sock.sendto(b"offline", ("198.51.100.1", 53))


def test_internal_socketpair_remains_available_for_asyncio_wakeup_only():
    first, second = socket.socketpair()
    try:
        first.sendall(b"x")
        assert second.recv(1) == b"x"
    finally:
        first.close()
        second.close()
