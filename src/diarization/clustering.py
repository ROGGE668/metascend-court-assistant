"""Online speaker clustering based on cosine similarity."""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class OnlineClustering:
    """Assign speaker IDs incrementally and update centroids with EMA."""

    def __init__(
        self,
        threshold: float = 0.65,
        max_speakers: int = 4,
        ema_alpha: float = 0.3,
    ):
        self.threshold = threshold
        self.max_speakers = max_speakers
        self.ema_alpha = ema_alpha
        self._centroids: dict[str, np.ndarray] = {}
        self._last_active: dict[str, int] = {}
        self._counter = 0

    def assign(self, embedding: np.ndarray, timestamp: int = 0) -> str:
        """Assign a speaker ID to the embedding."""
        best_id = None
        best_score = -1.0
        for sid, centroid in self._centroids.items():
            score = self._cosine_similarity(embedding, centroid)
            if score > best_score:
                best_score = score
                best_id = sid

        if best_id is not None and best_score >= self.threshold:
            self._update_centroid(best_id, embedding)
            self._last_active[best_id] = timestamp
            return best_id

        # Create new speaker
        if len(self._centroids) >= self.max_speakers:
            # Evict least recently active speaker
            oldest = min(self._last_active, key=self._last_active.get)
            logger.debug("Evicting speaker %s", oldest)
            del self._centroids[oldest]
            del self._last_active[oldest]

        new_id = f"SPEAKER_{self._counter:02d}"
        self._counter += 1
        self._centroids[new_id] = embedding.copy()
        self._last_active[new_id] = timestamp
        return new_id

    def get_centroid(self, speaker_id: str) -> np.ndarray | None:
        return self._centroids.get(speaker_id)

    def reset(self) -> None:
        self._centroids.clear()
        self._last_active.clear()
        self._counter = 0

    def _update_centroid(self, speaker_id: str, embedding: np.ndarray) -> None:
        old = self._centroids[speaker_id]
        self._centroids[speaker_id] = self.ema_alpha * embedding + (1 - self.ema_alpha) * old

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))
