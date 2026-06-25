# Metascend 庭审助手 - Agent Context

## Project Mission
以 **本地优先** 方式构建 **macOS 案件工作台**，面向普通人提供本地案件辅助。当前版本完整运行在 MacBook Air/Pro（M1-M5，16GB+）上，默认无云端依赖。

## Current Repo Layout
- `src/`: Python source, local backend, and model integrations
- `tests/`: pytest unit/integration tests
- `frontend/`: Tauri 2 + React/TypeScript desktop shell and macOS-style UI
- `scripts/download_models.py`: local model prefetch
- `docs/`: user, deployment, architecture, and phase guide docs
- `docs/guides/`: phased implementation guides
- `design/`: UI design assets and browser fixture pages
- `data/`: local cases, evidence, knowledge base, recordings, templates, users

## 当前阶段
**Phase 1-5 后端已完成**：本地音频采集 → VAD → 说话人分离 → ASR → 法律策略 → 可选 TTS。

前端已切换为 **Tauri 2 + React/TypeScript**；旧版 Python/Tk 与 `pywebview` 桌面 UI 已停止维护。

All reasoning is local. No cloud APIs are used by default.

## Architecture Constraints
- Python 3.11+ managed by `uv`
- Local models only: Whisper, pyannote, Ollama/Qwen, BGE
- Audio input: MacBook built-in microphone or Bluetooth headset
- Frontend: Tauri 2 + React/TypeScript on macOS
- Config via `.env` + `src/config.py`

## Key Directories
- `src/`: local backend, ASR, diarization, legal, TTS, pipeline
- `frontend/`: Tauri app shell, pages, styles
- `tests/`: pytest unit and integration tests
- `scripts/download_models.py`: download all local models
- `docs/`: architecture, deployment, privacy, user manual
- `docs/guides/`: phased implementation guides
- `design/`: UI design references and normalized fixture browser pages
- `data/`: local knowledge base, templates, encrypted recordings

## Commands
- `uv sync` - install dependencies
- `uv run pytest -m "not slow"` - run fast tests
- `uv run pytest --run-slow` - run all tests including model-loading tests
- `uv run python scripts/download_models.py` - download models
- `cd frontend && npm run dev` - run the new frontend preview
- `uv run python -m src.pipeline` - start local backend for integration testing
- `uv run black src tests scripts` - format code
- `uv run ruff check src tests scripts` - lint

## Rules
1. Never add cloud-only APIs or services.
2. Keep dependencies minimal for each phase.
3. All model downloads must be scriptable and cacheable.
4. Write tests for every module (audio, ASR, diarization, legal, TTS, pipeline).
5. Add docstrings in English or Chinese for public functions.
6. Prefer `pathlib` over `os.path`.
7. Use `logging` instead of `print` for module diagnostics.
8. All outputs must include the legal disclaimer.
9. Mock heavy models (LLM, embedding, TTS) in unit tests to keep CI fast.

## Legal Disclaimer
All outputs from this system are **reference suggestions only**, not legal advice. Users must retain final decision-making authority. Include a disclaimer in all UI outputs.
