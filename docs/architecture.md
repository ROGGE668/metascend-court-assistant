# Metascend 庭审助手 Architecture

## Overview

本地优先的模块化 macOS 案件工作台。前端桌面壳采用 Tauri 2；Python 侧仍负责本地模型与推理后端。

## Current Implementation (Phase 1)

```
Microphone -> AudioCapture -> VADBuffer -> ASREngine -> Local Backend API -> Tauri Frontend
```

Modules:
- `src/audio/capture.py`: sounddevice-based capture at 16kHz
- `src/audio/vad.py`: Silero VAD speech segmentation
- `src/asr/engine.py`: faster-whisper local transcription
- `frontend/`: Tauri 2 + React/TypeScript 桌面界面
- `src/pipeline.py`: orchestration and graceful shutdown

## Future Phases

```
Phase 2: + Speaker Diarization
Microphone -> AudioCapture -> VADBuffer -> Diarization -> ASREngine -> Local Backend API -> Tauri Frontend
                                            |
                                            v
                                   Role binding (judge/opponent/self/witness)

Phase 3: + Legal Brain
... -> ASREngine -> IntentExtractor -> RAG -> Local LLM -> StrategyGenerator -> Local Backend API -> Tauri Frontend
                                             |
                                             v
                                      KnowledgeBase (laws/cases/templates)

Phase 4: + TTS Output
... -> StrategyGenerator -> TTSEngine -> AudioOutput (bone-conduction/Bluetooth headset)
                                    |
                                    v
                             Audio ducking while user speaks
```

## Module Map

| Directory | Phase | Responsibility |
|-----------|-------|----------------|
| `src/audio/` | 1 | Capture, VAD, playback control |
| `src/asr/` | 1 | Whisper ASR, hotwords |
| `src/diarization/` | 2 | Speaker embedding, online clustering, role binding |
| `src/legal/` | 3 | Intent extraction, RAG retrieval, LLM strategy generation, risk filter |
| `src/tts/` | 4 | Local TTS, audio ducking, output routing |
| `frontend/` | 1-4 | Tauri desktop UI, Work/Chat/KB/Settings/Users |
| `src/pipeline.py` | 1-4 | Main orchestration |

## Threading Model

- Audio capture runs in sounddevice's internal callback thread.
- Main audio processing loop runs in a daemon thread.
- Tauri frontend runs in WebView；后端事件通过命令/事件接口传递。
- All cross-thread communication uses `queue.Queue`.
- Heavy models (LLM) should run in separate processes to avoid blocking ASR/VAD.

## Data Flow

1. Callback writes audio chunks to `AudioCapture._queue`.
2. `_capture_loop()` reads chunks and feeds `VADBuffer`.
3. When VAD emits a speech segment, it is tagged by diarization (Phase 2).
4. ASR transcribes the segment.
5. Transcription flows to the legal brain (Phase 3) for intent + strategy.
6. Strategy text is displayed and optionally spoken by TTS (Phase 4).

## Configuration

All runtime config is loaded from `.env` via `src/config.py`.

## Model Cache

Local models are cached under `~/.cache/metascend/models`. Use `uv run python scripts/download_models.py` to pre-download.
