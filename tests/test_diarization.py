"""Tests for speaker diarization and role binding."""

import numpy as np
import pytest

from src.data_types import Role
from src.diarization.clustering import OnlineClustering
from src.diarization.embedding import SpeakerEmbeddingExtractor
from src.diarization.engine import DiarizationEngine
from src.diarization.role_binding import RoleBinding


def _sine_wave(freq: float, duration: float = 1.0, sample_rate: int = 16000) -> np.ndarray:
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.3


def test_mock_embedding_distinguishes_frequencies():
    extractor = SpeakerEmbeddingExtractor(backend="mock")
    a = extractor.extract(_sine_wave(200))
    b = extractor.extract(_sine_wave(800))
    sim = extractor.cosine_similarity(a, b)
    assert 0.0 <= sim <= 1.0
    assert sim < 0.95  # different frequencies should differ


def test_clustering_assigns_same_speaker():
    extractor = SpeakerEmbeddingExtractor(backend="mock")
    clustering = OnlineClustering(threshold=0.65)
    emb = extractor.extract(_sine_wave(300))
    id1 = clustering.assign(emb)
    id2 = clustering.assign(emb)
    assert id1 == id2


def test_clustering_creates_new_speaker():
    extractor = SpeakerEmbeddingExtractor(backend="mock")
    clustering = OnlineClustering(threshold=0.95)
    id1 = clustering.assign(extractor.extract(_sine_wave(200)))
    id2 = clustering.assign(extractor.extract(_sine_wave(1000)))
    assert id1 != id2


def test_role_binding():
    extractor = SpeakerEmbeddingExtractor(backend="mock")
    binding = RoleBinding()
    binding.calibrate(Role.JUDGE, _sine_wave(250), extractor)
    binding.calibrate(Role.OPPONENT, _sine_wave(750), extractor)

    judge_emb = extractor.extract(_sine_wave(260))
    opp_emb = extractor.extract(_sine_wave(740))

    role_judge = binding.assign_role("S01", judge_emb, extractor)
    role_opp = binding.assign_role("S02", opp_emb, extractor)

    assert role_judge == Role.JUDGE
    assert role_opp == Role.OPPONENT


def test_diarization_engine_mock():
    engine = DiarizationEngine(backend="mock")
    engine.calibrate(Role.JUDGE, _sine_wave(250))
    engine.calibrate(Role.OPPONENT, _sine_wave(750))

    seg_judge = engine.process(_sine_wave(255, duration=1.5))
    seg_opp = engine.process(_sine_wave(745, duration=1.5))

    assert len(seg_judge) == 1
    assert len(seg_opp) == 1
    assert seg_judge[0].role == Role.JUDGE
    assert seg_opp[0].role == Role.OPPONENT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
