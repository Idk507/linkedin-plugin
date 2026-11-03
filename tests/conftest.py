"""Offline test defaults: ordinary tests must never reach external services."""

import socket
from ipaddress import ip_address

import pytest


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    """Reject external sockets; allow loopback for Windows asyncio internals."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def is_loopback(address):
        try:
            return isinstance(address, tuple) and ip_address(address[0]).is_loopback
        except ValueError:
            return False

    def connect(sock, address):
        if not is_loopback(address):
            raise AssertionError("External network access is disabled in offline tests")
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if not is_loopback(address):
            raise AssertionError("External network access is disabled in offline tests")
        return original_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
