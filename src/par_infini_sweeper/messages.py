import socketserver
from dataclasses import dataclass

from textual.message import Message


@dataclass
class ShowURL(Message):
    url: str


@dataclass
class WebServerStarted(Message):
    server: socketserver.TCPServer


@dataclass
class WebServerStopped(Message):
    pass


@dataclass
class AuthServerError(Message):
    """Posted when the OAuth loopback callback listener fails to bind.

    ARC-018: the previous ``start_auth_server`` let the ``OSError`` from a
    port-1999 collision propagate (or just crashed the auth flow silently).
    We now catch it and surface a clear, user-facing error instead.
    """

    error: str
