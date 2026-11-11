"""Short-lived in-memory store for callback payloads (Telegram callback_data is limited to 64 bytes)."""
from __future__ import annotations

import time
from typing import Any
from uuid import uuid4


class TokenStore:
    def __init__(self, ttl: int = 3600, max_items: int = 5000) -> None:
        self.ttl = ttl
        self.max_items = max_items
        self._data: dict[str, tuple[Any, float]] = {}

    def _purge(self) -> None:
        now = time.time()
        for k in [k for k, (_, ts) in self._data.items() if now - ts > self.ttl]:
            self._data.pop(k, None)
        while len(self._data) > self.max_items:  # drop oldest
            self._data.pop(next(iter(self._data)), None)

    def put(self, obj: Any) -> str:
        self._purge()
        token = uuid4().hex[:10]
        self._data[token] = (obj, time.time())
        return token

    def get(self, token: str) -> Any | None:
        entry = self._data.get(token)
        if not entry:
            return None
        if time.time() - entry[1] > self.ttl:
            self._data.pop(token, None)
            return None
        return entry[0]


store = TokenStore()