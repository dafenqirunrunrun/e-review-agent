from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    window_size: int = 10
    cooldown_seconds: int = 30
    state: str = "CLOSED"
    opened_at: float | None = None
    events: deque[bool] = field(default_factory=lambda: deque(maxlen=10))

    def record_success(self) -> None:
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.events.clear()
        self.events.append(True)

    def record_failure(self) -> None:
        self.events.append(False)
        if list(self.events).count(False) >= self.failure_threshold:
            self.state = "OPEN"
            self.opened_at = time.time()

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN" and self.opened_at and time.time() - self.opened_at >= self.cooldown_seconds:
            self.state = "HALF_OPEN"
            return True
        return self.state == "HALF_OPEN"
