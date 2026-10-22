"""Suite-wide test setup: loopback-only network guard and emulator fixtures.

The guard (requirement-1, ac-2) refuses every socket connection, datagram and name
lookup that is not loopback, for the whole pytest process. Tests must never reach a real
heat pump, a DNS server or the internet.

pytest-homeassistant-custom-component also blocks sockets per test through pytest-socket,
and a test that needs the emulator requests ``socket_enabled``. pytest-socket replaces
``socket.socket.connect`` and ``socket.getaddrinfo`` around every test and restores the
versions it captured at import time, which predate this guard. So the guard wraps
whatever is current, outermost, before and after every test (``trylast`` hooks run
after pytest-socket's), and its error names the refused address.
"""

from __future__ import annotations

import functools
import ipaddress
import socket
from collections.abc import AsyncIterator, Callable

import pytest
import pytest_socket
from genesis_wp.emulator import Emulator
from genesis_wp.emulator import get_profile

from .harness import PROFILE_615

pytest_plugins = "pytest_homeassistant_custom_component"


class NetworkGuardError(OSError):
    """Raised instead of a non-loopback network operation during tests."""


def _is_loopback_host(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode()
    if not isinstance(host, str):
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False  # a name other than localhost would need a DNS lookup


def _check_address(sock: socket.socket, address) -> None:
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return  # AF_UNIX and friends never leave the host
    if not _is_loopback_host(address[0]):
        raise NetworkGuardError(
            f"test network guard: only loopback is allowed, refused {address!r}"
        )


def _check_host(host) -> None:
    if host is not None and not _is_loopback_host(host):
        raise NetworkGuardError(
            f"test network guard: only loopback is allowed, refused lookup of {host!r}"
        )


def _guarded(func, check):
    """Wrap ``func`` so ``check`` runs first; never wrap a wrapper twice."""
    if getattr(func, "_loopback_guard", False):
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        check(*args)
        return func(*args, **kwargs)

    wrapper._loopback_guard = True
    return wrapper


def _install_guard() -> None:
    real_socket = pytest_socket._true_socket  # the class, even while pytest-socket swaps it
    real_socket.connect = _guarded(real_socket.connect, _check_address)
    real_socket.connect_ex = _guarded(real_socket.connect_ex, _check_address)
    real_socket.sendto = _guarded(
        real_socket.sendto, lambda sock, data, *args: _check_address(sock, args[-1])
    )
    socket.getaddrinfo = _guarded(socket.getaddrinfo, lambda host, *args: _check_host(host))


_install_guard()


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item) -> None:
    _install_guard()


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem) -> None:
    _install_guard()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/genesis_wp in every test."""
    yield


@pytest.fixture
async def start_emulator(socket_enabled) -> AsyncIterator[Callable[..., Emulator]]:
    """Factory: ``await start_emulator(profile_name, **options)`` -> running Emulator on a free loopback port."""
    running: list[Emulator] = []

    async def start(profile: str = PROFILE_615, **options) -> Emulator:
        emu = Emulator(get_profile(profile), port=0, **options)
        await emu.start()
        running.append(emu)
        return emu

    yield start
    for emu in running:
        await emu.stop()
