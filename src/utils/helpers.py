"""General helper functions."""

import time
from collections import deque


class MovingAverage:
    """Thread-safe enough moving average for single producer/consumer."""

    def __init__(self, window: int = 10):
        self.window = window
        self._values: deque[float] = deque(maxlen=window)

    def add(self, value: float) -> None:
        self._values.append(value)

    @property
    def average(self) -> float:
        if not self._values:
            return 0.0
        return sum(self._values) / len(self._values)

    def reset(self) -> None:
        self._values.clear()


def current_time_ms() -> int:
    return int(time.time() * 1000)
