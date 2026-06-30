#!/usr/bin/env python3
"""MLX 推理 sidecar 服务器。

由 Rust Tauri 后端启动和管理，提供 LLM 推理 HTTP API。
模型：Qwen3.5-9B-MLX-4bit（ModelScope / HuggingFace）
框架：Apple MLX（mlx-lm）

端点：
  GET  /health     - 健康检查
  POST /chat       - 单轮/多轮对话
  POST /reset      - 清空对话历史
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ── 日志 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("mlx_server")

# ── 配置 ──────────────────────────────────────────────
PORT = int(os.environ.get("METASCEND_PORT", "8727"))
MODEL_ID = os.environ.get(
    "MLX_MODEL_ID",
    "mlx-community/Qwen3.5-9B-MLX-4bit",
)
MODEL_CACHE_DIR = os.path.expanduser(
    os.environ.get(
        "MLX_MODEL_DIR",
        os.path.expanduser("~/.cache/metascend/models/mlx"),
    )
)
SYSTEM_PROMPT = (
    "You are a professional legal assistant for Chinese law. "
    "Answer concisely and accurately. Reply in the same language as the user."
)
MODELSCOPE_REPO = "mlx-community/Qwen3.5-9B-MLX-4bit"

# ── 全局状态 ──────────────────────────────────────────
_model = None
_tokenizer = None
_history: list[dict] = []  # [{role, content}, ...]
_model_loading = False
_model_error: Optional[str] = None


def _download_from_modelscope(repo_id: str, local_dir: str) -> str:
    """从 ModelScope 下载模型文件到本地目录。"""
    os.makedirs(local_dir, exist_ok=True)
    import subprocess

    parts = repo_id.split("/")
    namespace = parts[0] if len(parts) == 2 else "mlx-community"
    model_name = parts[-1]

    # 获取文件列表
    tree_url = f"https://www.modelscope.cn/api/v1/models/{namespace}/{model_name}/repo/tree?Revision=master&RootPath="
    log.info("Fetching file list from ModelScope: %s", tree_url)

    import urllib.request
    try:
        req = urllib.request.Request(tree_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        files = data.get("Data", [])
    except Exception as e:
        log.warning("Failed to list ModelScope files: %s, falling back to known files", e)
        # 回退到已知文件列表
        files = [
            {"Name": "config.json"},
            {"Name": "tokenizer.json"},
            {"Name": "tokenizer_config.json"},
            {"Name": "chat_template.jinja"},
            {"Name": "vocab.json"},
            {"Name": "model.safetensors.index.json"},
            {"Name": "model-00001-of-00002.safetensors"},
            {"Name": "model-00002-of-00002.safetensors"},
        ]

    for f in files:
        fname = f.get("Name", "")
        if not fname or fname.endswith("/") or fname.startswith("."):
            continue

        dest = os.path.join(local_dir, fname)
        if os.path.exists(dest):
            log.info("Already downloaded: %s", fname)
            continue

        # 使用 urllib 下载（避免依赖 requests）
        url = f"https://www.modelscope.cn/models/{namespace}/{model_name}/resolve/master/{fname}"
        log.info("Downloading %s from ModelScope...", fname)
        try:
            urllib.request.urlretrieve(url, dest)
            log.info("Downloaded: %s (%.1f MB)", fname, os.path.getsize(dest) / 1e6)
        except Exception as e:
            log.error("Failed to download %s: %s", fname, e)
            raise

    return local_dir


def _ensure_model_local() -> str:
    """确保模型文件在本地可用，返回本地路径。"""
    # 检查是否已是本地路径
    if os.path.isdir(MODEL_ID) and os.path.exists(os.path.join(MODEL_ID, "config.json")):
        return MODEL_ID

    # 本地缓存目录
    safe_name = MODEL_ID.replace("/", "--")
    local_dir = os.path.join(MODEL_CACHE_DIR, safe_name)

    if os.path.isdir(local_dir) and os.path.exists(os.path.join(local_dir, "config.json")):
        log.info("Model found in local cache: %s", local_dir)
        return local_dir

    # 从 ModelScope 下载
    log.info("Downloading model from ModelScope: %s", MODEL_ID)
    return _download_from_modelscope(MODEL_ID, local_dir)


def _load_model():
    """延迟加载模型（首次调用时）。"""
    global _model, _tokenizer, _model_loading, _model_error
    if _model is not None:
        return
    if _model_loading:
        return
    _model_loading = True
    _model_error = None

    try:
        import mlx_lm

        local_path = _ensure_model_local()
        log.info("Loading model from: %s", local_path)

        _model, _tokenizer = mlx_lm.load(local_path)
        log.info("Model loaded successfully")
    except Exception as e:
        _model_error = str(e)
        log.error("Model load failed: %s", e)
        _model_loading = False
        raise
    _model_loading = False


# ── FastAPI 应用 ──────────────────────────────────────

def create_app():
    """创建 FastAPI 应用，带懒加载。"""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel

    app = FastAPI(title="Metascend MLX Server")

    class ChatRequest(BaseModel):
        message: str
        system: Optional[str] = None
        max_tokens: Optional[int] = 512
        temperature: Optional[float] = 0.7

    class ChatResponse(BaseModel):
        reply: str
        model: str
        history_length: int

    @app.get("/health")
    async def health():
        if _model_error:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": _model_error},
            )
        return {
            "status": "ok",
            "model": MODEL_ID,
            "ready": _model is not None,
            "loading": _model_loading,
            "history_length": len(_history),
        }

    @app.post("/chat")
    async def chat(req: ChatRequest):
        global _history

        if _model is None and not _model_loading:
            try:
                _load_model()
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"Model load failed: {e}")

        if _model_loading:
            raise HTTPException(status_code=503, detail="Model is still loading")

        if _model is None:
            raise HTTPException(status_code=503, detail="Model not available")

        try:
            import mlx_lm

            system_text = req.system or SYSTEM_PROMPT
            messages = [{"role": "system", "content": system_text}]
            messages.extend(_history)
            messages.append({"role": "user", "content": req.message})

            prompt = _tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=False,
            )

            from mlx_lm.sample_utils import make_sampler
            sampler = make_sampler(temp=req.temperature or 0.7, top_p=0.9)

            t0 = time.time()
            reply = mlx_lm.generate(
                _model,
                _tokenizer,
                prompt=prompt,
                max_tokens=req.max_tokens or 512,
                sampler=sampler,
            )
            elapsed = time.time() - t0

            reply = reply.strip()
            log.info("Chat reply in %.1fs (%d chars)", elapsed, len(reply))

            _history.append({"role": "user", "content": req.message})
            _history.append({"role": "assistant", "content": reply})

            if len(_history) > 40:
                _history = _history[-40:]

            return ChatResponse(reply=reply, model=MODEL_ID, history_length=len(_history))

        except Exception as e:
            log.error("Chat error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/reset")
    async def reset():
        global _history
        _history.clear()
        return {"status": "ok", "message": "History cleared"}

    @app.get("/model")
    async def model_info():
        return {
            "model_id": MODEL_ID,
            "model_dir": MODEL_CACHE_DIR,
            "ready": _model is not None,
            "loading": _model_loading,
            "error": _model_error,
        }

    return app


def main():
    try:
        import uvicorn
    except ImportError:
        log.error("uvicorn not installed. Run: pip install uvicorn fastapi mlx-lm")
        sys.exit(1)

    log.info("Starting MLX server on port %d, model=%s", PORT, MODEL_ID)
    log.info("Model cache dir: %s", MODEL_CACHE_DIR)

    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")


if __name__ == "__main__":
    main()
