# 说话人角色绑定

import logging

import numpy as np

from src.data_types import Role
from src.diarization.embedding import SpeakerEmbeddingExtractor

logger = logging.getLogger(__name__)


class RoleBinding:
    """Bind speaker IDs to courtroom roles via calibrated embeddings."""

    def __init__(self, similarity_threshold: float = 0.60):
        self.threshold = similarity_threshold
        self._role_embeddings: dict[Role, np.ndarray] = {}

    def calibrate(
        self,
        role: Role,
        audio: np.ndarray,
        extractor: SpeakerEmbeddingExtractor,
    ) -> None:
        """Record a 5-second voice sample for a role."""
        embedding = extractor.extract(audio)
        self._role_embeddings[role] = embedding
        logger.info("Calibrated role %s", role.value)

    def assign_role(
        self,
        speaker_id: str,
        centroid: np.ndarray,
        extractor: SpeakerEmbeddingExtractor,
    ) -> Role:
        """Assign the closest role to a speaker centroid."""
        best_role = Role.UNKNOWN
        best_score = 0.0
        for role, emb in self._role_embeddings.items():
            score = extractor.cosine_similarity(centroid, emb)
            if score > best_score:
                best_score = score
                best_role = role

        if best_score >= self.threshold:
            logger.debug(
                "Assigned role %s to %s (score %.2f)",
                best_role.value,
                speaker_id,
                best_score,
            )
            return best_role
        return Role.UNKNOWN

    def reset(self) -> None:
        self._role_embeddings.clear()

    def is_calibrated(self, role: Role) -> bool:
        return role in self._role_embeddings
