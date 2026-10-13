import os
import time
import struct
import sqlite3
import hashlib
import logging
import threading
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from llama_index.core import Settings
from llama_index.core.schema import TextNode
from backend.config import settings, CACHE_DIR, MODEL_CACHE_DIR

logger = logging.getLogger(__name__)

_embed_model_lock = threading.Lock()
_embed_model_instance = None

DB_PATH = CACHE_DIR / "embedding_cache.db"

class PersistentEmbeddingCache:
    """
    High-performance SQLite-backed persistent embedding cache.
    Stores dense vectors indexed by (model_name, content_hash).
    Guarantees unchanged chunks are never re-embedded across restarts.
    """
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self):
        try:
            conn = self._get_conn()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chunk_embeddings (
                        model_name TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        dim INTEGER NOT NULL,
                        vector BLOB NOT NULL,
                        created_at REAL NOT NULL,
                        PRIMARY KEY (model_name, content_hash)
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_lookup ON chunk_embeddings(model_name, content_hash)")
        except Exception as e:
            logger.warning("Error initializing embedding cache DB: %s", e)

    @staticmethod
    def _pack_vector(vec: List[float]) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def _unpack_vector(blob: bytes, dim: int) -> List[float]:
        return list(struct.unpack(f"{dim}f", blob))

    def get_many(self, model_name: str, hashes: List[str]) -> Dict[str, List[float]]:
        if not hashes:
            return {}
        result: Dict[str, List[float]] = {}
        try:
            conn = self._get_conn()
            # Batch query in chunks of 500
            for i in range(0, len(hashes), 500):
                batch = hashes[i:i + 500]
                placeholders = ",".join("?" for _ in batch)
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT content_hash, dim, vector FROM chunk_embeddings WHERE model_name = ? AND content_hash IN ({placeholders})",
                    [model_name] + batch
                )
                for h, dim, blob in cursor.fetchall():
                    result[h] = self._unpack_vector(blob, dim)
        except Exception as e:
            logger.warning("Error reading from embedding cache: %s", e)
        return result

    def set_many(self, model_name: str, items: Dict[str, List[float]]):
        if not items:
            return
        try:
            conn = self._get_conn()
            now = time.time()
            rows = [
                (model_name, h, len(vec), self._pack_vector(vec), now)
                for h, vec in items.items()
            ]
            with conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO chunk_embeddings (model_name, content_hash, dim, vector, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, rows)
        except Exception as e:
            logger.warning("Error writing to embedding cache: %s", e)

    def count(self) -> int:
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM chunk_embeddings")
            row = cursor.fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

embedding_cache = PersistentEmbeddingCache()

def _check_local_cache_available(model_name: str) -> bool:
    """Checks if the model directory already exists in model_cache."""
    normalized = model_name.replace("/", "--")
    candidate_dirs = [
        MODEL_CACHE_DIR / f"models--{normalized}",
        MODEL_CACHE_DIR / normalized
    ]
    for d in candidate_dirs:
        if d.exists() and (d / "snapshots").exists():
            return True
    return False

def get_embedding_model():
    """Thread-safe singleton accessor for the embedding model with offline-first loading."""
    global _embed_model_instance
    if _embed_model_instance is not None:
        return _embed_model_instance
    
    with _embed_model_lock:
        if _embed_model_instance is not None:
            return _embed_model_instance

        # Enable offline mode if model already cached to avoid slow HuggingFace Hub network checks
        is_cached = _check_local_cache_available(settings.embedding_model_name)
        if is_cached:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            logger.info("Local model snapshot found in %s; operating offline-first.", MODEL_CACHE_DIR)
        
        try:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            logger.info("Initializing HuggingFaceEmbedding: %s on %s", settings.embedding_model_name, settings.device)
            embed_model = HuggingFaceEmbedding(
                model_name=settings.embedding_model_name,
                device=settings.device,
                cache_folder=str(MODEL_CACHE_DIR)
            )
            # Verify test embedding
            _ = embed_model.get_text_embedding("test")
            _embed_model_instance = embed_model
            Settings.embed_model = embed_model
            return _embed_model_instance
        except Exception as e:
            logger.warning("Standard HuggingFaceEmbedding initialization encountered notice (%s), trying Custom SentenceTransformer...", e)
            
        try:
            from sentence_transformers import SentenceTransformer
            from llama_index.core.embeddings import BaseEmbedding
            
            class CustomHFEmbedding(BaseEmbedding):
                def __init__(self, model_name: str, **kwargs):
                    super().__init__(**kwargs)
                    self._model = SentenceTransformer(
                        model_name,
                        cache_folder=str(MODEL_CACHE_DIR),
                        device=settings.device
                    )
                
                def _get_query_embedding(self, query: str) -> List[float]:
                    return self._model.encode(query, show_progress_bar=False).tolist()
                
                def _get_text_embedding(self, text: str) -> List[float]:
                    return self._model.encode(text, show_progress_bar=False).tolist()
                
                def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
                    return self._model.encode(texts, batch_size=32, show_progress_bar=False).tolist()
                
                async def _aget_query_embedding(self, query: str) -> List[float]:
                    return self._get_query_embedding(query)
                
                async def _aget_text_embedding(self, text: str) -> List[float]:
                    return self._get_text_embedding(text)
            
            embed_model = CustomHFEmbedding(model_name=settings.embedding_model_name)
            _ = embed_model.get_text_embedding("test")
            _embed_model_instance = embed_model
            Settings.embed_model = embed_model
            return _embed_model_instance
        except Exception as e2:
            logger.error("Failed to load SentenceTransformer fallback: %s", e2)
            raise RuntimeError(f"Embedding model initialization failed: {e2}")

def compute_chunk_content_hash(text: str) -> str:
    """Computes a stable SHA-256 content digest for embedding caching."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:32]

def embed_nodes_batch(nodes: List[TextNode], batch_size: int = 32) -> Tuple[List[TextNode], int, int]:
    """
    Batches chunk embedding computation with persistent SQLite cache.
    Returns: (nodes_with_embeddings, cache_hits, computed_count)
    """
    if not nodes:
        return [], 0, 0

    model = get_embedding_model()
    model_name = settings.embedding_model_name
    
    # 1. Map each node to its content hash
    node_hashes = []
    for node in nodes:
        c_hash = node.metadata.get("content_hash") or compute_chunk_content_hash(node.get_content())
        node.metadata["content_hash"] = c_hash
        node_hashes.append(c_hash)

    # 2. Check persistent cache
    unique_hashes = list(set(node_hashes))
    cached_vectors = embedding_cache.get_many(model_name, unique_hashes)
    
    # 3. Identify missing hashes
    missing_hashes = [h for h in unique_hashes if h not in cached_vectors]
    
    cache_hits = len(unique_hashes) - len(missing_hashes)
    computed_count = len(missing_hashes)
    
    if missing_hashes:
        # Build hash -> text lookup for first occurrence
        hash_to_text: Dict[str, str] = {}
        for node in nodes:
            h = node.metadata["content_hash"]
            if h in missing_hashes and h not in hash_to_text:
                hash_to_text[h] = node.get_content()

        missing_list = list(hash_to_text.keys())
        texts_to_embed = [hash_to_text[h] for h in missing_list]
        
        logger.info("Computing embeddings for %d new chunks in batches of %d...", len(texts_to_embed), batch_size)
        
        newly_computed: Dict[str, List[float]] = {}
        for i in range(0, len(texts_to_embed), batch_size):
            batch_slice = texts_to_embed[i:i + batch_size]
            batch_hashes = missing_list[i:i + batch_size]
            if hasattr(model, "_get_text_embeddings"):
                batch_vecs = model._get_text_embeddings(batch_slice)
            elif hasattr(model, "get_text_embedding_batch"):
                batch_vecs = model.get_text_embedding_batch(batch_slice)
            else:
                batch_vecs = [model.get_text_embedding(t) for t in batch_slice]

            for h, vec in zip(batch_hashes, batch_vecs):
                newly_computed[h] = vec
                cached_vectors[h] = vec

        # Save new embeddings to persistent database
        embedding_cache.set_many(model_name, newly_computed)
        logger.info("Persisted %d newly computed vectors to embedding cache.", len(newly_computed))

    # 4. Attach vector embeddings to TextNodes
    for node in nodes:
        h = node.metadata["content_hash"]
        vec = cached_vectors.get(h)
        if vec:
            node.embedding = vec

    return nodes, cache_hits, computed_count

def compute_query_embedding(query: str) -> List[float]:
    """Generates query vector embedding using the configured model."""
    model = get_embedding_model()
    return model.get_query_embedding(query)
