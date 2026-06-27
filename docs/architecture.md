# Metascend 庭审助手 Architecture

## Overview

本地优先的模块化 macOS 案件工作台。前端桌面壳与后端均采用 **Tauri 2 + Rust**，不再依赖 Python 运行时。

## Current Implementation (Phase A)

```
Tauri Frontend (React/TypeScript)
        |
        v
Tauri Rust Backend (invoke commands)
        |
        +---> CaseStore      -> JSON files
        +---> EvidenceStore  -> Local files
        +---> KnowledgeStore -> Local knowledge base files
        +---> SettingsStore  -> JSON settings
        +---> AIStub         -> Placeholder for future AI features
```

Modules:
- `frontend/src-tauri/src/cases.rs`: case JSON persistence
- `frontend/src-tauri/src/evidence.rs`: evidence file import/list/delete
- `frontend/src-tauri/src/knowledge.rs`: knowledge base metadata and content
- `frontend/src-tauri/src/store.rs`: runtime settings persistence
- `frontend/src-tauri/src/ai_stub.rs`: courtroom/chat/calibration stubs
- `frontend/src/`: Tauri 2 + React/TypeScript desktop UI
- `frontend/src-tauri/src/lib.rs`: Tauri command registration and app lifecycle

## Future Phases

```
Phase B: + Audio capture + VAD (Rust cpal + local VAD model)
Phase C: + ASR + Speaker diarization (whisper-rs / ONNX)
Phase D: + Legal Brain (local embedding + rules + optional local LLM)
Phase E: + TTS output (local ONNX TTS)
```

## Module Map

| Directory | Phase | Responsibility |
|-----------|-------|----------------|
| `frontend/src-tauri/src/cases.rs` | A | Case JSON CRUD |
| `frontend/src-tauri/src/evidence.rs` | A | Evidence file management |
| `frontend/src-tauri/src/knowledge.rs` | A | Knowledge base metadata |
| `frontend/src-tauri/src/store.rs` | A | Runtime settings |
| `frontend/src-tauri/src/ai_stub.rs` | A | Placeholder AI commands |
| `frontend/src/` | A | Tauri desktop UI |

## Threading Model

- Tauri frontend runs in WebView; backend commands run on `tauri::async_runtime`.
- All disk IO uses `tokio::fs` to avoid blocking the runtime.
- Future audio capture will run in a dedicated thread/cpal stream.
- Heavy models (ASR/LLM/TTS) will be loaded lazily and run in background tasks.

## Data Flow

1. Frontend invokes a Tauri command.
2. Rust backend reads/writes local JSON or file system.
3. AI commands currently return stub responses; future phases will add real inference.

## Configuration

Runtime settings are persisted in `app_data_dir/settings.json` by `SettingsStore`.

## Model Cache

No models are bundled in Phase A. Future phases will cache local models under a Rust-managed directory (e.g., `app_data_dir/models`).
