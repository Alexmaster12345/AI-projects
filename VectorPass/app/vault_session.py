from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class VaultKey:
    user_id: int
    key: bytes
    expires_at: float


class VaultKeyCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_session: dict[str, VaultKey] = {}

    def set(self, session_id: str, user_id: int, key: bytes, ttl_seconds: int) -> None:
        now = time.time()
        with self._lock:
            self._by_session[session_id] = VaultKey(user_id=user_id, key=key, expires_at=now + ttl_seconds)

    def get(self, session_id: str, user_id: int) -> Optional[bytes]:
        now = time.time()
        with self._lock:
            vk = self._by_session.get(session_id)
            if vk is None:
                return None
            if vk.user_id != user_id:
                return None
            if vk.expires_at < now:
                self._by_session.pop(session_id, None)
                return None
            return vk.key

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._by_session.pop(session_id, None)

    def clear_all_for_user(self, user_id: int) -> None:
        with self._lock:
            for sid, vk in list(self._by_session.items()):
                if vk.user_id == user_id:
                    self._by_session.pop(sid, None)
