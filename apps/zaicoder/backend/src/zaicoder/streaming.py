"""UI-framework-independent helpers for streamed responses."""

from __future__ import annotations


class StreamRenderGate:
    """Coalesce high-frequency deltas into bounded UI renders."""

    def __init__(self, *, interval_seconds: float = 1 / 30, char_threshold: int = 96):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if char_threshold <= 0:
            raise ValueError("char_threshold must be positive")
        self.interval_seconds = interval_seconds
        self.char_threshold = char_threshold
        self._last_rendered_at: float | None = None
        self._chars_since_render = 0

    def should_render(self, delta: str, now: float) -> bool:
        """Record a delta and return whether the caller should render now."""
        self._chars_since_render += len(delta)
        if self._last_rendered_at is None:
            return self._flush(now)
        if self._chars_since_render >= self.char_threshold:
            return self._flush(now)
        if now - self._last_rendered_at >= self.interval_seconds:
            return self._flush(now)
        return False

    def flush(self, now: float) -> bool:
        """Force a final render after a stream finishes."""
        if self._chars_since_render == 0:
            return False
        return self._flush(now)

    def _flush(self, now: float) -> bool:
        self._last_rendered_at = now
        self._chars_since_render = 0
        return True
