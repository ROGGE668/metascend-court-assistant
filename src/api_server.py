"""FastAPI HTTP bridge between the Tauri frontend and the Python backend.

The Rust shell starts this server as a managed child process and forwards
`invoke` calls as HTTP requests to `localhost`.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from src.case_archive import CaseArchive
from src.config import Config, configure_logging
from src.data_types import Role
from src.evidence.store import EvidenceStore
from src.legal.knowledge_base import LocalLegalKnowledgeBase
from src.pipeline import CourtAssistantPipeline

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Pydantic request/response models
# --------------------------------------------------------------------------- #
class CreateCaseRequest(BaseModel):
    title: str
    case_type: str = "other"


class ImportEvidenceRequest(BaseModel):
    source_path: str


class SearchKnowledgeRequest(BaseModel):
    query: str
    category: str | None = None
    top_k: int = 5


class ChatAskRequest(BaseModel):
    message: str


class CalibrateRequest(BaseModel):
    role: str


class SettingsUpdate(BaseModel):
    toggles: dict[str, bool] | None = None


# --------------------------------------------------------------------------- #
# Simple runtime settings store
# --------------------------------------------------------------------------- #
class SettingsStore:
    """Persist user-facing toggles to a JSON file in the data directory.

    This is intentionally separate from `.env` so the frontend can save
    settings without rewriting environment variables at runtime.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Config.DATA_DIR / "runtime_settings.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._defaults()
        try:
            with open(self.path, encoding="utf-8") as fp:
                data = json.load(fp)
            if not isinstance(data, dict):
                return self._defaults()
            return data
        except Exception:
            logger.warning("Failed to load runtime settings, using defaults")
            return self._defaults()

    def _defaults(self) -> dict[str, Any]:
        return {
            "diarization": Config.ENABLE_DIARIZATION,
            "hotword": len(Config.ASR_HOTWORDS) > 0,
            "legal": Config.ENABLE_LEGAL_ASSISTANT,
            "tts": Config.ENABLE_TTS,
            "recording": Config.ENABLE_RECORDING,
            "diary": Config.ENABLE_ENCRYPTED_LOGS,
        }

    def get(self) -> dict[str, Any]:
        return self._data

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        self._data.update(updates)
        with open(self.path, "w", encoding="utf-8") as fp:
            json.dump(self._data, fp, ensure_ascii=False, indent=2)
        return self._data


# --------------------------------------------------------------------------- #
# App factory and dependency injection
# --------------------------------------------------------------------------- #
class AppDependencies:
    """Container for the backend singletons used by the API."""

    def __init__(
        self,
        pipeline: CourtAssistantPipeline | None = None,
        case_archive: CaseArchive | None = None,
        evidence_store: EvidenceStore | None = None,
        knowledge_base: LocalLegalKnowledgeBase | None = None,
        settings_store: SettingsStore | None = None,
    ) -> None:
        self.pipeline = pipeline or CourtAssistantPipeline(lazy_init=True)
        self.case_archive = case_archive or CaseArchive()
        self.evidence_store = evidence_store or EvidenceStore()
        self.knowledge_base = knowledge_base or LocalLegalKnowledgeBase()
        self.settings_store = settings_store or SettingsStore()

    def load_knowledge(self) -> None:
        try:
            self.knowledge_base.load()
        except Exception:
            logger.exception("Knowledge base load failed; falling back to built-ins on demand")


def create_app(dependencies: AppDependencies | None = None) -> FastAPI:
    deps = dependencies or AppDependencies()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        configure_logging()
        logger.info("Starting Metascend API server")
        deps.load_knowledge()
        deps.pipeline.start()
        yield
        deps.pipeline.stop()
        logger.info("Metascend API server stopped")

    app = FastAPI(title="Metascend Court Assistant API", lifespan=lifespan)

    # ------------------------------------------------------------------ #
    # Health & status
    # ------------------------------------------------------------------ #
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "disclaimer": "本系统输出仅供参考，不构成法律意见。"}

    @app.get("/status")
    async def status() -> dict:
        return deps.pipeline.get_status()

    # ------------------------------------------------------------------ #
    # Realtime courtroom
    # ------------------------------------------------------------------ #
    @app.post("/courtroom/start")
    async def courtroom_start() -> dict:
        running = deps.pipeline.toggle_courtroom(True)
        return {"courtroom_running": running}

    @app.post("/courtroom/stop")
    async def courtroom_stop() -> dict:
        running = deps.pipeline.toggle_courtroom(False)
        return {"courtroom_running": running}

    @app.get("/transcript")
    async def transcript() -> dict:
        return {"transcript": deps.pipeline.get_transcript()}

    @app.get("/suggestion")
    async def suggestion() -> dict:
        return deps.pipeline.get_suggestion()

    @app.post("/calibrate")
    async def calibrate(req: CalibrateRequest) -> dict:
        role_map = {
            "法官": Role.JUDGE,
            "己方": Role.SELF,
            "对方": Role.OPPONENT,
        }
        role = role_map.get(req.role, Role.UNKNOWN)
        if role == Role.UNKNOWN:
            return {"ok": False, "error": f"未知角色: {req.role}"}
        # Placeholder: real calibration needs a recorded audio sample from the frontend.
        import numpy as np

        ok = deps.pipeline.calibrate_role(role, np.zeros(16000, dtype=np.float32))
        return {"ok": ok, "role": req.role}

    # ------------------------------------------------------------------ #
    # Cases & evidence
    # ------------------------------------------------------------------ #
    @app.get("/cases")
    async def list_cases() -> list[dict]:
        return deps.case_archive.list_cases()

    @app.post("/cases")
    async def create_case(req: CreateCaseRequest) -> dict:
        case = deps.case_archive.create_case(req.title, req.case_type)
        return case.to_dict()

    @app.get("/cases/{case_id}")
    async def get_case(case_id: str) -> dict:
        case = deps.case_archive.load(case_id)
        if case is None:
            return {"error": "Case not found"}
        return case.to_dict()

    @app.get("/evidence")
    async def list_evidence() -> list[dict]:
        return deps.evidence_store.list()

    @app.post("/evidence/import")
    async def import_evidence(req: ImportEvidenceRequest) -> dict:
        try:
            dest = deps.evidence_store.import_file(req.source_path)
            return {"ok": True, "path": str(dest)}
        except Exception as e:
            logger.exception("Evidence import failed")
            return {"ok": False, "error": str(e)}

    @app.delete("/evidence/{name}")
    async def delete_evidence(name: str) -> dict:
        try:
            deps.evidence_store.delete(name)
            return {"ok": True}
        except Exception as e:
            logger.exception("Evidence delete failed")
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    # Knowledge base
    # ------------------------------------------------------------------ #
    @app.get("/knowledge")
    async def list_knowledge() -> dict:
        return {
            "documents": deps.knowledge_base.list_documents(),
            "total": len(deps.knowledge_base._docs),
            "engine": "ChromaDB",
            "embedding_model": Config.EMBEDDING_MODEL,
        }

    @app.post("/knowledge/search")
    async def search_knowledge(req: SearchKnowledgeRequest) -> dict:
        results = deps.knowledge_base.search(req.query, category=req.category, top_k=req.top_k)
        return {"query": req.query, "results": results}

    # ------------------------------------------------------------------ #
    # Chat / post-session analysis
    # ------------------------------------------------------------------ #
    @app.post("/chat/ask")
    async def chat_ask(req: ChatAskRequest) -> dict:
        deps.pipeline.state.add_chat_message("User", req.message, "")
        return deps.pipeline.chat_ask(req.message)

    @app.get("/chat/messages")
    async def chat_messages() -> list[dict]:
        return deps.pipeline.get_chat_messages()

    # ------------------------------------------------------------------ #
    # Settings
    # ------------------------------------------------------------------ #
    @app.get("/settings")
    async def get_settings() -> dict:
        return {
            "toggles": deps.settings_store.get(),
            "asr_model": Config.ASR_MODEL_SIZE,
            "llm_model": Config.LLM_MODEL,
            "embedding_model": Config.EMBEDDING_MODEL,
            "data_dir": str(Config.DATA_DIR),
        }

    @app.post("/settings")
    async def save_settings(req: SettingsUpdate) -> dict:
        toggles = req.toggles or {}
        deps.settings_store.update(toggles)
        return deps.settings_store.get()

    return app


def main() -> int:
    import uvicorn

    configure_logging()
    # Rust sidecar passes the chosen port via METASCEND_PORT; fall back to the
    # legacy METASCEND_API_PORT / .env value for standalone runs.
    port = int(os.getenv("METASCEND_PORT") or os.getenv("METASCEND_API_PORT", "8727"))
    host = os.getenv("METASCEND_API_HOST", "127.0.0.1")
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level=Config.LOG_LEVEL.lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
