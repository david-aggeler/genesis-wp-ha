"""The suite may only talk to the loopback interface (requirement-1)."""

from __future__ import annotations

import asyncio
import socket

import pytest

# RFC 5737 TEST-NET-1: documentation range, never routed. The guard must refuse it
# before any packet leaves.
OUTSIDE = ("192.0.2.1", 502)


def _names(exc: BaseException, what: str) -> bool:
    return "loopback" in str(exc) and what in str(exc)


# DHF-REQ: genesis-wp-ha/requirement-1  DHF-TEST: genesis-wp-ha/ac-2
def test_tcp_connect_outside_loopback_is_refused(socket_enabled):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        with pytest.raises(OSError) as info:
            sock.connect(OUTSIDE)
    assert _names(info.value, OUTSIDE[0])


# DHF-REQ: genesis-wp-ha/requirement-1  DHF-TEST: genesis-wp-ha/ac-2
def test_connect_ex_and_udp_outside_loopback_are_refused(socket_enabled):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(OSError) as info:
            sock.connect_ex(OUTSIDE)
        assert _names(info.value, OUTSIDE[0])
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        with pytest.raises(OSError) as info:
            sock.sendto(b"x", OUTSIDE)
        assert _names(info.value, OUTSIDE[0])


# DHF-REQ: genesis-wp-ha/requirement-1  DHF-TEST: genesis-wp-ha/ac-2
def test_name_lookup_is_refused(socket_enabled):
    with pytest.raises(OSError) as info:
        socket.getaddrinfo("heatpump.example", 502)
    assert _names(info.value, "heatpump.example")


# DHF-REQ: genesis-wp-ha/requirement-1  DHF-TEST: genesis-wp-ha/ac-2
async def test_asyncio_connection_outside_loopback_is_refused(socket_enabled):
    with pytest.raises(OSError) as info:
        await asyncio.wait_for(asyncio.open_connection(*OUTSIDE), timeout=2)
    assert _names(info.value, OUTSIDE[0])


def test_loopback_is_allowed(socket_enabled):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.create_connection(server.getsockname(), timeout=2):
            pass
