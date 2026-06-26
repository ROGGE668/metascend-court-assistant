"""Speaker embedding extraction with pyannote and mock backends."""

import logging
from pathlib import Path

import numpy as np

from src.config import Config

logger = logging.getLogger(__name__)


class SpeakerEmbeddingExtractor:
    """Extract speaker embeddings from 16kHz mono audio."""

    _model_cache = None

    def __init__(
        self,
        backend: str = "pyannote",
        model_name: str = "pyannote/wespeaker-voxceleb-resnet34-LM",
        cache_dir: Path = Config.MODEL_CACHE_DIR,
    ):
        self.backend = backend
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None

    def _load_model(self):
        if self.backend == "mock":
            return None
        if SpeakerEmbeddingExtractor._model_cache is not None:
            return SpeakerEmbeddingExtractor._model_cache
        logger.info("Loading speaker embedding model: %s", self.model_name)
        try:
            from pyannote.audio import Model

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            model = Model.from_pretrained(
                self.model_name,
                cache_dir=str(self.cache_dir),
                use_auth_token=False,
                local_files_only=True,
            )
            SpeakerEmbeddingExtractor._model_cache = model
            return model
        except Exception as e:
            logger.warning("Failed to load pyannote embedding model: %s. Falling back to mock.", e)
            self.backend = "mock"
            return None

    def extract(self, audio: np.ndarray) -> np.ndarray:
        """Return a fixed-size embedding vector."""
        audio = audio.astype(np.float32).reshape(-1)
        if self.backend == "mock":
            return self._mock_embedding(audio)

        if self._model is None:
            self._model = self._load_model()
        if self._model is None:
            return self._mock_embedding(audio)

        import torch

        waveform = torch.from_numpy(audio).unsqueeze(0)
        with torch.no_grad():
            embedding = self._model(waveform)
            if isinstance(embedding, torch.Tensor):
                embedding = embedding.squeeze().cpu().numpy()
        return embedding.astype(np.float32)

    @staticmethod
    def _mock_embedding(audio: np.ndarray, dim: int = 256) -> np.ndarray:
        """Deterministic lightweight embedding based on the dominant frequency.

        A Gaussian spectrum centred at the peak frequency makes small
        frequency drift (e.g. 250 Hz vs 260 Hz) highly similar, while
        well-separated tones (e.g. 250 Hz vs 750 Hz) are nearly orthogonal.
        """
        audio = audio.astype(np.float64).reshape(-1)
        energy = float(np.sqrt(np.mean(audio**2)))
        if energy < 1e-6:
            vec = np.zeros(dim, dtype=np.float32)
            vec[0] = 1.0
            return vec / (np.linalg.norm(vec) + 1e-10)

        window = np.hanning(len(audio)) * audio
        fft = np.abs(np.fft.rfft(window))
        freqs = np.fft.rfftfreq(len(audio), d=1.0 / 16000)
        peak_freq = float(freqs[int(np.argmax(fft))])

        # Map peak frequency to a bin coordinate in [0, dim - 1].
        center = (peak_freq / 8000.0) * (dim - 1)
        sigma = 4.0  # bins; controls how much frequency drift is tolerated
        idxs = np.arange(dim, dtype=np.float64)
        vec = np.exp(-((idxs - center) ** 2) / (2.0 * sigma**2)).astype(np.float32)
        vec *= energy
        return vec / (np.linalg.norm(vec) + 1e-10)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))
