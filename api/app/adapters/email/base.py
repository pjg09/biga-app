from typing import Protocol


class EmailAdapter(Protocol):
    def send(self, to: str, subject: str, html: str) -> None:
        ...
