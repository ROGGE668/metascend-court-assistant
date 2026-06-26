"""FastAPI HTTP sidecar for the Tauri frontend.

The Rust shell starts this server as a managed child process.  It only
exposes AI/inference endpoints.  Pure data CRUD (cases, evidence, settings,
knowledge metadata) is handled directly by the Rust layer.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from src.config import Config, configure_logging
from src.data_types import Role
from src.legal.knowledge_base import LocalLegalKnowledgeBase
from src.pipeline import CourtAssistantPipeline

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Pydantic request/response models
# --------------------------------------------------------------------------- #
class SearchKnowledgeRequest(BaseModel):
    query: str
    category: str | None = None
    top_k: int = 5


class ChatAskRequest(BaseModel):
    message: str


class CalibrateRequest(BaseModel):
    role: str


# --------------------------------------------------------------------------- #
# App factory and dependency injection
# --------------------------------------------------------------------------- #
class AppDependencies:
    """Container for the backend singletons used by the API."""

    def __init__(
        self,
        pipeline: CourtAssistantPipeline | None = None,
        knowledge_base: LocalLegalKnowledgeBase | None = None,
    ) -> None:
        self.pipeline = pipeline or CourtAssistantPipeline(lazy_init=True)
        self.knowledge_base = knowledge_base or LocalLegalKnowledgeBase()

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
    # Knowledge base search (Rust owns metadata; Python handles vector search)
    # ------------------------------------------------------------------ #
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
