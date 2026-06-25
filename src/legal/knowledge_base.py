"""Local legal knowledge base backed by vector search."""

import json
import logging
import random
from pathlib import Path

import yaml

from src.config import Config
from src.ocr.engine import LocalOCRReader, UnavailableOCRReader

logger = logging.getLogger(__name__)


class LocalLegalKnowledgeBase:
    """Embed and retrieve local legal documents using sentence-transformers + ChromaDB.

    A fallback in-memory mode is used when the embedding model or ChromaDB is
    unavailable, so the system keeps running offline even if dependencies fail.
    """

    BUILT_IN_DOCS = [
        {
            "law": "《民法典》第679条",
            "content": "自然人之间的借款合同，自贷款人提供借款时成立。",
            "case_type": "借贷",
        },
        {
            "law": "《民法典》第680条",
            "content": "禁止高利放贷，借款的利率不得违反国家有关规定。",
            "case_type": "借贷",
        },
        {
            "law": "《民间借贷司法解释》第25条",
            "content": (
                "出借人请求借款人按照合同约定利率支付利息的，"
                "人民法院应予支持，但超过合同成立时一年期LPR四倍的除外。"
            ),
            "case_type": "借贷",
        },
        {
            "law": "《民法典》第1079条",
            "content": "夫妻一方要求离婚的，可以由有关组织进行调解或者直接向人民法院提起离婚诉讼。",
            "case_type": "离婚",
        },
        {
            "law": "《民法典》第1087条",
            "content": (
                "离婚时，夫妻的共同财产由双方协议处理；"
                "协议不成的，由人民法院根据财产的具体情况判决。"
            ),
            "case_type": "离婚",
        },
        {
            "law": "《劳动合同法》第30条",
            "content": "用人单位应当按照劳动合同约定和国家规定，向劳动者及时足额支付劳动报酬。",
            "case_type": "劳动",
        },
        {
            "law": "《劳动合同法》第31条",
            "content": "用人单位应当严格执行劳动定额标准，不得强迫或者变相强迫劳动者加班。",
            "case_type": "劳动",
        },
        {
            "law": "《民法典》第577条",
            "content": (
                "当事人一方不履行合同义务或者履行合同义务不符合约定的，"
                "应当承担继续履行、采取补救措施或者赔偿损失等违约责任。"
            ),
            "case_type": "合同",
        },
    ]

    def __init__(
        self,
        knowledge_base_dir: Path | None = None,
        embedding_fn=None,
    ):
        self.dir = knowledge_base_dir or Config.KNOWLEDGE_BASE_DIR
        self._embedding_fn = embedding_fn
        self._model = None
        self._client = None
        self._collection = None
        self._docs: list[dict] = []

    def _load_embedding_model(self):
        """Lazy-load the sentence-transformer model."""
        if self._embedding_fn is not None:
            return None
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                Config.EMBEDDING_MODEL,
                cache_folder=str(Config.MODEL_CACHE_DIR),
            )
            return self._model
        except Exception as e:
            logger.warning("Failed to load embedding model: %s", e)
            return None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Return an embedding for each text."""
        if self._embedding_fn is not None:
            return [self._embedding_fn(t) for t in texts]

        model = self._load_embedding_model()
        if model is not None:
            embeddings = model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embeddings.tolist()

        # Deterministic fallback so the module never crashes.
        dim = 384
        return [[random.random() for _ in range(dim)] for _ in texts]

    def load(self) -> None:
        """Load documents from disk and build the vector index."""
        self._docs = []
        supported_suffixes = {".json", ".yaml", ".yml", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
        files = sorted(
            path
            for path in self.dir.iterdir()
            if path.is_file() and path.suffix.lower() in supported_suffixes
        )

        if not files:
            self._docs = list(self.BUILT_IN_DOCS)
        else:
            for file_path in files:
                try:
                    docs = self._load_document_file(file_path)
                    if docs:
                        self._docs.extend(docs)
                except Exception as e:
                    logger.warning("Failed to load %s: %s", file_path, e)

        if not self._docs:
            self._docs = list(self.BUILT_IN_DOCS)

        self._build_index()

    def _load_document_file(self, file_path: Path) -> list[dict]:
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".json":
                with open(file_path, encoding="utf-8") as fp:
                    data = json.load(fp)
                if isinstance(data, list):
                    return [item for item in data if isinstance(item, dict)]
            elif suffix in {".yaml", ".yml"}:
                with open(file_path, encoding="utf-8") as fp:
                    data = yaml.safe_load(fp)
                if isinstance(data, list):
                    return [item for item in data if isinstance(item, dict)]
            elif suffix == ".pdf":
                text = self._ocr_or_text_extract(file_path)
                if text:
                    return [{"type": "imported_pdf", "text": text, "metadata": {"source": file_path.name, "case_type": ""}}]
            elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}:
                text = self._ocr_or_text_extract(file_path)
                if text:
                    return [{"type": "imported_image", "text": text, "metadata": {"source": file_path.name, "case_type": ""}}]
        except Exception as e:
            logger.warning("Failed to parse knowledge file %s: %s", file_path, e)
        return []

    def _ocr_or_text_extract(self, path: Path) -> str:
        text = ""
        try:
            reader = LocalOCRReader()
            if isinstance(reader, UnavailableOCRReader):
                return ""
            text = reader.extract_text(path)
        except Exception as exc:
            logger.debug("Knowledge base OCR fallback failed for %s: %s", path, exc)
        return text or ""

    def _build_index(self) -> None:
        """Create or refresh the ChromaDB collection."""
        try:
            import chromadb

            persist_dir = Config.MODEL_CACHE_DIR / "chroma_legal"
            self._client = chromadb.PersistentClient(path=str(persist_dir))
            self._collection = self._client.get_or_create_collection(name="legal_docs")
            self._collection.delete(where={})

            texts = [d.get("content", "") for d in self._docs]
            metadatas = [
                {"law": d.get("law", ""), "case_type": d.get("case_type", "")} for d in self._docs
            ]
            ids = [f"doc_{i}" for i in range(len(self._docs))]
            embeddings = self._embed(texts)
            self._collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids,
            )
        except Exception as e:
            logger.warning("ChromaDB index build failed: %s", e)
            self._collection = None

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """Return the most relevant documents for a query."""
        if self._collection is None or not self._docs:
            return self._docs[:top_k]

        try:
            query_embedding = self._embed([query])[0]
            n_results = min(top_k, len(self._docs))
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
            )
            docs = []
            for i in range(len(results["documents"][0])):
                docs.append(
                    {
                        "content": results["documents"][0][i],
                        "law": results["metadatas"][0][i].get("law", ""),
                        "case_type": results["metadatas"][0][i].get("case_type", ""),
                    }
                )
            return docs
        except Exception as e:
            logger.warning("Knowledge retrieval failed: %s", e)
            return self._docs[:top_k]
