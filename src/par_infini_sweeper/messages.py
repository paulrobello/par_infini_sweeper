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
