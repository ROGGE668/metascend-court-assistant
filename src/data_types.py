"""Shared datatypes used across modules."""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from src.case_archive.models import CaseFile

__all__ = [
    "Role",
    "AudioFrame",
    "SpeechSegment",
    "SpeakerSegment",
    "TranscriptLine",
    "LegalIntent",
    "Strategy",
    "CaseFile",
    "Status",
]


class Role(Enum):
    JUDGE = "法官"
    SELF = "己方"
    OPPONENT = "对方"
    WITNESS = "证人"
    UNKNOWN = "未知"


class Status(Enum):
    """Realtime pipeline status exposed to the Tauri frontend."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    ERROR = "error"


@dataclass
class AudioFrame:
    samples: np.ndarray
    sample_rate: int = 16000
    timestamp_ms: int = 0
    source: str = "microphone"


@dataclass
class SpeechSegment:
    audio: np.ndarray
    start_ms: int
    end_ms: int
    source: str = "microphone"


@dataclass
class SpeakerSegment:
    audio: np.ndarray
    start_ms: int
    end_ms: int
    speaker_id: str
    role: Role = Role.UNKNOWN


@dataclass
class TranscriptLine:
    text: str
    start_ms: int
    end_ms: int
    speaker_id: str = "SPEAKER_00"
    role: Role = Role.UNKNOWN
    confidence: float | None = None


@dataclass
class LegalIntent:
    claim: str | None = None
    evidence: str | None = None
    objection: bool = False
    legal_ground: str | None = None
    case_type: str | None = None
    raw_text: str = ""


@dataclass
class Strategy:
    text: str = ""
    reasoning: str = ""
    risk_level: str = "low"  # low / medium / high
    source: str = "rule"  # rule / rag / llm
    referenced_laws: list[str] = field(default_factory=list)
    countermeasure: str = ""
