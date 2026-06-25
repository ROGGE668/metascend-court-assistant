"""Tests for the end-to-end pipeline orchestration."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.data_types import Role, SpeakerSegment, Strategy, TranscriptLine
from src.pipeline import CourtAssistantPipeline


def _collect_updates(pipeline: CourtAssistantPipeline):
    """Replace the UI update method with a recorder."""
    updates = []
    pipeline.state.update = lambda msg, status=None: updates.append((msg, status))
    return updates


def test_format_transcript_line_known_role():
    pipeline = CourtAssistantPipeline(
        enable_diarization=False,
        enable_legal=False,
        enable_tts=False,
    )
    line = TranscriptLine(
        text="请陈述你的意见",
        start_ms=0,
        end_ms=1000,
        speaker_id="S01",
        role=Role.JUDGE,
    )
    assert pipeline._format_transcript_line(line) == "[法官] 请陈述你的意见"


def test_format_transcript_line_unknown_role():
    pipeline = CourtAssistantPipeline(
        enable_diarization=False,
        enable_legal=False,
        enable_tts=False,
    )
    line = TranscriptLine(
        text="未识别",
        start_ms=0,
        end_ms=1000,
        speaker_id="S02",
        role=Role.UNKNOWN,
    )
    assert pipeline._format_transcript_line(line) == "[S02] 未识别"


def test_pipeline_with_diarization():
    pipeline = CourtAssistantPipeline(
        enable_diarization=True,
        enable_legal=False,
        enable_tts=False,
    )
    pipeline._diarization = MagicMock()
    pipeline._diarization.process.return_value = [
        SpeakerSegment(
            audio=np.zeros(16000, dtype=np.float32),
            start_ms=0,
            end_ms=1000,
            speaker_id="S01",
            role=Role.JUDGE,
        )
    ]
    pipeline._asr.transcribe_segment = lambda seg: TranscriptLine(
        text="请回答",
        start_ms=seg.start_ms,
        end_ms=seg.end_ms,
        speaker_id=seg.speaker_id,
        role=seg.role,
    )
    updates = _collect_updates(pipeline)
    pipeline._process_speech_segment(np.zeros(16000, dtype=np.float32))
    messages = [msg for msg, _ in updates]
    assert any("[法官] 请回答" in msg for msg in messages)


def test_pipeline_with_legal_and_tts():
    pipeline = CourtAssistantPipeline(
        enable_diarization=False,
        enable_legal=False,
        enable_tts=False,
    )
    pipeline._asr.transcribe = lambda _audio: "我要求对方还款"
    pipeline._legal = MagicMock()
    pipeline._legal.suggest.return_value = Strategy(
        text="核对借条原件",
        referenced_laws=["《民法典》第679条"],
        risk_level="low",
    )
    pipeline._tts = MagicMock()

    updates = _collect_updates(pipeline)
    suggestions = []
    pipeline.state.update_suggestion = lambda text, laws: suggestions.append((text, laws))

    pipeline._process_speech_segment(np.zeros(16000, dtype=np.float32))

    messages = [msg for msg, _ in updates]
    assert any("我要求对方还款" in msg for msg in messages)
    assert any("核对借条原件" == text for text, _ in suggestions)
    assert any("《民法典》第679条" in ", ".join(laws) for _, laws in suggestions)
    pipeline._tts.speak.assert_called_once()


def test_pipeline_chat_send():
    """Chat-mode legal Q&A should use LegalAssistant and post an AI reply."""
    pipeline = CourtAssistantPipeline(
        enable_diarization=False,
        enable_legal=False,
        enable_tts=False,
    )

    with patch("src.pipeline.LegalAssistant") as mock_cls:
        assistant = MagicMock()
        assistant.suggest.return_value = Strategy(
            text="要求对方说明还款时间、地点及资金来源",
            referenced_laws=["《民法典》第679条"],
        )
        mock_cls.return_value = assistant

        result = pipeline.chat_ask("对方说现金还清了，没有收据")

    assistant.suggest.assert_called_once_with("对方说现金还清了，没有收据")
    assert result["sender"] == "AI"
    assert "说明还款时间" in result["text"]
    assert "《民法典》第679条" in result["ref"]
    assert any(m["sender"] == "AI" for m in pipeline.state.chat_messages)


def test_pipeline_chat_send_failure_handled():
    """Chat-mode should gracefully report an error if LegalAssistant fails."""
    pipeline = CourtAssistantPipeline(
        enable_diarization=False,
        enable_legal=False,
        enable_tts=False,
    )

    with patch("src.pipeline.LegalAssistant") as mock_cls:
        mock_cls.side_effect = RuntimeError("模型加载失败")
        result = pipeline.chat_ask("问一个法律问题")

    assert result["sender"] == "AI"
    assert "无法调用法律助手" in result["text"]
    assert any(m["sender"] == "AI" for m in pipeline.state.chat_messages)


def test_pipeline_calibrate_role_success():
    """calibrate_role should forward the sample to diarization and return True."""
    pipeline = CourtAssistantPipeline(
        enable_diarization=True,
        enable_legal=False,
        enable_tts=False,
    )
    pipeline._diarization = MagicMock()
    audio = np.zeros(16000, dtype=np.float32)
    ok = pipeline.calibrate_role(Role.JUDGE, audio)
    assert ok is True
    pipeline._diarization.calibrate.assert_called_once_with(Role.JUDGE, audio)


def test_pipeline_calibrate_role_disabled():
    """calibrate_role should return False when diarization is disabled."""
    pipeline = CourtAssistantPipeline(
        enable_diarization=False,
        enable_legal=False,
        enable_tts=False,
    )
    audio = np.zeros(16000, dtype=np.float32)
    ok = pipeline.calibrate_role(Role.SELF, audio)
    assert ok is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
