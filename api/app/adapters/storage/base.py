from typing import Protocol


class StorageAdapter(Protocol):
    def upload(self, key: str, data: bytes, content_type: str) -> str:
        ...

    def get_url(self, key: str) -> str:
        ...
