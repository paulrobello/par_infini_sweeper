from dataclasses import dataclass

from textual.message import Message


@dataclass
class ShowURL(Message):
    url: str
