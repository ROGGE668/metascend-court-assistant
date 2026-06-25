# 说话人分离引擎

import logging

import numpy as np

from src.config import Config
from src.data_types import Role, SpeakerSegment
from src.diarization.clustering import OnlineClustering
from src.diarization.embedding import SpeakerEmbeddingExtractor
from src.diarization.role_binding import RoleBinding

logger = logging.getLogger(__name__)


class DiarizationEngine:
    """End-to-end diarization: embedding + clustering + role binding."""

    def __init__(
        self,
        sample_rate: int = Config.SAMPLE_RATE,
        backend: str = "pyannote",
        similarity_threshold: float = 0.65,
        role_threshold: float = 0.60,
        max_speakers: int = 4,
        cache_dir=None,
    ):
        self.sample_rate = sample_rate
        self._extractor = SpeakerEmbeddingExtractor(
            backend=backend,
            cache_dir=cache_dir or Config.MODEL_CACHE_DIR,
        )
        self._clustering = OnlineClustering(
            threshold=similarity_threshold,
            max_speakers=max_speakers,
        )
        self._role_binding = RoleBinding(similarity_threshold=role_threshold)
        self._timestamp = 0

    def calibrate(self, role: Role, audio: np.ndarray) -> None:
        """Calibrate a role with a voice sample."""
        self._role_binding.calibrate(role, audio, self._extractor)

    def process(self, audio: np.ndarray) -> list[SpeakerSegment]:
        """Process a VAD speech segment and return tagged speaker segments."""
        audio = audio.astype(np.float32).reshape(-1)
        duration_ms = int(len(audio) / self.sample_rate * 1000)
        embedding = self._extractor.extract(audio)
        speaker_id = self._clustering.assign(embedding, timestamp=self._timestamp)
        self._timestamp += duration_ms

        centroid = self._clustering.get_centroid(speaker_id)
        if centroid is None:
            centroid = embedding

        role = self._role_binding.assign_role(speaker_id, centroid, self._extractor)

        return [
            SpeakerSegment(
                audio=audio,
                start_ms=self._timestamp - duration_ms,
                end_ms=self._timestamp,
                speaker_id=speaker_id,
                role=role,
            )
        ]

    def reset(self) -> None:
        self._clustering.reset()
        self._role_binding.reset()
        self._timestamp = 0

    @property
    def is_calibrated(self) -> bool:
        return any(
            self._role_binding.is_calibrated(role)
            for role in [Role.JUDGE, Role.SELF, Role.OPPONENT]
        )
