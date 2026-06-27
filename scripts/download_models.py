"""Pre-download all local models to avoid runtime network access."""

import logging
import os
import sys
from pathlib import Path

from src.asr.engine import ASREngine
from src.config import Config, configure_logging

logger = logging.getLogger(__name__)


def download_whisper(cache_dir: Path) -> None:
    logger.info("Downloading faster-whisper model: %s", Config.ASR_MODEL_SIZE)
    engine = ASREngine(cache_dir=cache_dir)
    engine.load()
    engine.unload()
    logger.info("faster-whisper model ready")


def download_silero_vad() -> None:
    logger.info("Downloading Silero VAD model")
    import torch

    torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        onnx=False,
    )
    logger.info("Silero VAD model ready")


def download_pyannote(cache_dir: Path) -> None:
    logger.info("Downloading pyannote.audio models")
    try:
        from pyannote.audio import Model

        segmentation = Model.from_pretrained(
            "pyannote/segmentation-3.0",
            cache_dir=str(cache_dir),
            use_auth_token=False,
        )
        embedding = Model.from_pretrained(
            "pyannote/wespeaker-voxceleb-resnet34-LM",
            cache_dir=str(cache_dir),
            use_auth_token=False,
        )
        logger.info(
            "pyannote models ready: %s, %s",
            segmentation.__class__.__name__,
            embedding.__class__.__name__,
        )
    except Exception as e:
        logger.warning("Could not download pyannote models: %s", e)


def download_bge(cache_dir: Path) -> None:
    logger.info("Downloading BGE embedding model")
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            "BAAI/bge-large-zh-v1.5",
            cache_folder=str(cache_dir),
        )
        logger.info("BGE model ready: %s", model.get_sentence_embedding_dimension())
    except Exception as e:
        logger.warning("Could not download BGE model: %s", e)


def main() -> int:
    configure_logging()
    cache_dir = Config.MODEL_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Model cache directory: %s", cache_dir)

    hf_endpoint = os.getenv("HF_ENDPOINT", "https://huggingface.co")
    logger.info("Using Hugging Face endpoint: %s", hf_endpoint)

    download_whisper(cache_dir)
    download_silero_vad()
    download_pyannote(cache_dir)
    download_bge(cache_dir)

    logger.info("All model downloads attempted. You can now run offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
