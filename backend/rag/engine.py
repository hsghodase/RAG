import time
import json
import pickle
import hashlib
import logging
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Iterator, Set
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.schema import Document, TextNode

from backend.config import settings, CACHE_DIR
from backend.rag.embeddings import get_embedding_model, embed_nodes_batch, embedding_cache
from backend.rag.chunking import AdvancedChunker
from backend.rag.ingestion import IngestionPipeline, WikipediaLoader
from backend.rag.retrieval import RAGRetriever, RetrievedEvidence
from backend.rag.generation import RAGGenerator
from backend.rag.citations import CitationManager
from backend.rag.graph import KnowledgeGraphBuilder

logger = logging.getLogger(__name__)

KB_METADATA_FILE = CACHE_DIR / "knowledge_base.json"
HISTORY_FILE = CACHE_DIR / "article_history.json"

class IngestionTaskManager:
    """
    Lightweight, thread-safe asynchronous job tracker for article ingestion,
    reloading, and reprocessing. Allows real-time progress polling.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def create_task(self, name: str, total_items: int) -> str:
        with self._lock:
            task_id = f"task_{int(time.time() * 1000)}_{len(self._tasks) + 1}"
            self._tasks[task_id] = {
                "task_id": task_id,
                "name": name,
                "status": "queued",  # queued, running, completed, failed
                "stage": "Queued",   # Queued, Fetching, Cleaning, Chunking, Embedding, Indexing, Completed, Failed
                "progress": 0.0,
                "current_item": "",
                "total_items": total_items,
                "completed_items": 0,
                "failed_items": 0,
                "started_at": time.time(),
                "updated_at": time.time(),
                "elapsed_seconds": 0.0,
                "errors": [],
                "result_message": ""
            }
            return task_id

    def update_task(
        self,
        task_id: str,
        stage: str,
        progress: float,
        current_item: str = "",
        completed_delta: int = 0,
        failed_delta: int = 0,
        error: Optional[str] = None
    ):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["status"] = "running"
            task["stage"] = stage
            task["progress"] = min(1.0, max(0.0, progress))
            if current_item:
                task["current_item"] = current_item
            task["completed_items"] += completed_delta
            task["failed_items"] += failed_delta
            if error:
                task["errors"].append(error)
            task["updated_at"] = time.time()
            task["elapsed_seconds"] = round(time.time() - task["started_at"], 1)

    def complete_task(self, task_id: str, message: str, success: bool = True):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["status"] = "completed" if success else "failed"
            task["stage"] = "Completed" if success else "Failed"
            task["progress"] = 1.0
            task["result_message"] = message
            task["updated_at"] = time.time()
            task["elapsed_seconds"] = round(time.time() - task["started_at"], 1)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            copy = dict(task)
            if copy["status"] == "running":
                copy["elapsed_seconds"] = round(time.time() - copy["started_at"], 1)
            return copy

task_manager = IngestionTaskManager()

class RAGEngine:
    """
    Production-grade orchestrator for the Wikipedia RAG Platform.
    Manages:
    - Persistent Article Records with Staging-and-Commit updates
    - Section-Aware Token Chunking
    - Persistent Vector Caching & Batch Embeddings
    - Incremental Vector Indexing
    - Filter-aware, Token-budgeted Retrieval & Reranking
    - Fast Grounded Generation with Multi-model Fallback
    - 3D Knowledge Space Visualization
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.chunker = AdvancedChunker()
        self.ingestion = IngestionPipeline()
        self.generator = RAGGenerator()
        
        self.index: Optional[VectorStoreIndex] = None
        self.loaded_documents: List[Document] = []
        self.chunk_nodes: List[TextNode] = []
        self.doc_titles: List[str] = []
        self.doc_metadata_list: List[Dict[str, Any]] = []
        self.article_records: Dict[str, Dict[str, Any]] = {}
        
        self.chat_history: List[Dict[str, Any]] = []
        self.last_retrieved: List[RetrievedEvidence] = []
        self.last_query: Optional[str] = None
        self.article_history: List[Dict[str, Any]] = []
        
        self._load_state()

    def _load_state(self):
        """Loads article records, history, and auto-restores vector index on startup."""
        # 1. Load article records
        if KB_METADATA_FILE.exists():
            try:
                with open(KB_METADATA_FILE, "r", encoding="utf-8") as f:
                    self.article_records = json.load(f)
            except Exception as e:
                logger.warning("Could not read knowledge_base.json: %s", e)
                self.article_records = {}

        # 2. Load legacy article history
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.article_history = json.load(f)
            except Exception as e:
                logger.warning("Could not read article_history.json: %s", e)
                self.article_history = []

        # 3. Restore latest saved index cache
        self.load_latest_cache()

        # 4. Reconcile loaded records with index
        self._reconcile_state()

    def _save_state(self):
        """Atomically persists knowledge base records and history."""
        try:
            with open(KB_METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.article_records, f, indent=2)
        except Exception as e:
            logger.warning("Could not persist knowledge_base.json: %s", e)

        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.article_history, f, indent=2)
        except Exception as e:
            logger.warning("Could not persist article_history.json: %s", e)

    def _reconcile_state(self):
        """Ensures article_records, doc_titles, chunk_nodes, and history are synchronized."""
        active_titles = {t.strip().lower() for t in self.doc_titles}
        
        # Sync article_records into doc_metadata_list
        reconciled_meta = []
        for title in self.doc_titles:
            record = self._find_record_by_title(title)
            if record:
                reconciled_meta.append({
                    "article_id": record.get("article_id", ""),
                    "title": record.get("title", title),
                    "url": record.get("url", ""),
                    "char_count": record.get("char_count", 0),
                    "token_count": record.get("token_count", 0),
                    "chunks_count": record.get("chunks_count", 0),
                    "type": record.get("type", "wikipedia"),
                    "status": record.get("status", "indexed"),
                    "last_updated": record.get("last_updated", time.time())
                })
        if reconciled_meta:
            self.doc_metadata_list = reconciled_meta

        # Sync history items
        for item in self.article_history:
            item["is_active"] = item.get("title", "").strip().lower() in active_titles

    def _find_record_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        clean = title.strip().lower()
        for rec in self.article_records.values():
            if rec.get("title", "").strip().lower() == clean:
                return rec
        return None

    def _get_stable_article_id(self, title: str) -> str:
        clean_slug = "".join(c if c.isalnum() else "_" for c in title.lower())[:30].strip("_")
        digest = hashlib.md5(title.strip().encode("utf-8")).hexdigest()[:6]
        return f"{clean_slug}_{digest}"

    def get_articles_payload(self) -> Dict[str, Any]:
        """Returns comprehensive state for the Knowledge Base left panel."""
        active_set = {t.strip().lower() for t in self.doc_titles}
        
        all_articles = []
        # First add all tracked records
        seen_titles = set()
        for art_id, rec in self.article_records.items():
            t = rec.get("title", "")
            seen_titles.add(t.strip().lower())
            is_active = t.strip().lower() in active_set
            all_articles.append({
                "article_id": art_id,
                "title": t,
                "url": rec.get("url", ""),
                "char_count": rec.get("char_count", 0),
                "token_count": rec.get("token_count", 0),
                "chunks_count": rec.get("chunks_count", 0),
                "type": rec.get("type", "wikipedia"),
                "status": rec.get("status", "indexed" if is_active else "saved"),
                "last_error": rec.get("last_error"),
                "is_active": is_active,
                "loaded_at": rec.get("loaded_at", 0),
                "last_updated": rec.get("last_updated", 0)
            })

        # Add any active articles that might not have a record yet
        for doc in self.doc_metadata_list:
            t = doc.get("title", "")
            if t.strip().lower() not in seen_titles:
                seen_titles.add(t.strip().lower())
                all_articles.append({
                    "article_id": doc.get("article_id") or self._get_stable_article_id(t),
                    "title": t,
                    "url": doc.get("url", ""),
                    "char_count": doc.get("char_count", 0),
                    "token_count": doc.get("token_count", 0),
                    "chunks_count": doc.get("chunks_count", 0),
                    "type": doc.get("type", "wikipedia"),
                    "status": "indexed",
                    "last_error": None,
                    "is_active": True,
                    "loaded_at": time.time(),
                    "last_updated": time.time()
                })

        # Update article history
        for item in self.article_history:
            item["is_active"] = item.get("title", "").strip().lower() in active_set

        return {
            "count": len([a for a in all_articles if a["is_active"]]),
            "total_tracked": len(all_articles),
            "articles": all_articles,
            "total_chunks": len(self.chunk_nodes),
            "history": self.article_history,
            "cache_stats": {
                "cached_embeddings": embedding_cache.count(),
                "embedding_model": settings.embedding_model_name,
                "device": settings.device
            }
        }

    def load_latest_cache(self) -> bool:
        """Loads latest verified index cache file if present."""
        try:
            cache_files = sorted(CACHE_DIR.glob("rag_index_*.pkl"), key=lambda p: p.stat().st_mtime, reverse=True)
            for cache_path in cache_files:
                try:
                    with open(cache_path, "rb") as f:
                        data = pickle.load(f)
                    self.index = data["index"]
                    self.loaded_documents = data.get("documents", [])
                    self.chunk_nodes = data.get("chunks", [])
                    self.doc_titles = data.get("titles", [])
                    self.doc_metadata_list = data.get("metadata", [])
                    logger.info("Restored index from cache: %s (%d articles, %d chunks)",
                                cache_path.name, len(self.doc_titles), len(self.chunk_nodes))
                    return True
                except Exception as err:
                    logger.warning("Could not restore cache file %s: %s", cache_path, err)
        except Exception:
            pass
        return False

    def save_to_cache(self, titles: List[str]):
        """Persists index and document chunks to disk."""
        if not self.index or not self.chunk_nodes:
            return
        normalized = sorted([t.strip().lower() for t in titles])
        digest = hashlib.sha256(":::".join(normalized).encode()).hexdigest()[:16]
        cache_path = CACHE_DIR / f"rag_index_{digest}.pkl"
        try:
            data = {
                "index": self.index,
                "documents": self.loaded_documents,
                "chunks": self.chunk_nodes,
                "titles": self.doc_titles,
                "metadata": self.doc_metadata_list,
            }
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)
            logger.info("Persisted index cache: %s", cache_path.name)
        except Exception as e:
            logger.warning("Could not persist index cache: %s", e)

    def _rebuild_index_from_nodes(self):
        """Constructs VectorStoreIndex over current self.chunk_nodes."""
        if self.chunk_nodes:
            embed_model = get_embedding_model()
            self.index = VectorStoreIndex(
                nodes=self.chunk_nodes,
                embed_model=embed_model,
                show_progress=False
            )
            self.save_to_cache(self.doc_titles)
        else:
            self.index = None

    def ingest_wikipedia_articles(
        self,
        article_names: List[str],
        progress_cb: Optional[Any] = None,
        replace_existing: bool = False
    ) -> Tuple[bool, str, Dict[str, str]]:
        """Cumulative ingestion of Wikipedia articles."""
        clean_names = [n.strip() for n in article_names if n.strip()]
        if not clean_names:
            return False, "No article names specified.", {}

        with self._lock:
            existing_titles_set = {t.strip().lower() for t in self.doc_titles}
            names_to_fetch = [n for n in clean_names if n.strip().lower() not in existing_titles_set or replace_existing]
            already_loaded = [n for n in clean_names if n.strip().lower() in existing_titles_set and not replace_existing]
            
            status_map: Dict[str, str] = {t: "Already loaded in knowledge base" for t in already_loaded}

            if not names_to_fetch:
                return True, f"All {len(clean_names)} article(s) are already loaded in the knowledge base.", status_map

            if progress_cb:
                progress_cb("Fetching", f"Downloading {len(names_to_fetch)} Wikipedia article(s)...", 0.1)

            new_docs, fetch_status = self.ingestion.load_wikipedia_articles(names_to_fetch)
            status_map.update(fetch_status)

            if not new_docs:
                return False, f"Could not load articles ({', '.join(names_to_fetch)}). Please check Wikipedia titles.", status_map

            if progress_cb:
                progress_cb("Chunking", f"Splitting {len(new_docs)} document(s) into semantic chunks...", 0.4)

            new_chunks: List[TextNode] = []
            new_metas: List[Dict[str, Any]] = []

            for doc in new_docs:
                title = doc.metadata.get("title", "Article")
                art_id = self._get_stable_article_id(title)
                nodes = self.chunker.process_document(doc)
                new_chunks.extend(nodes)

                char_count = doc.metadata.get("char_count", len(doc.text))
                token_count = sum(n.metadata.get("token_count", 0) for n in nodes)
                chunks_count = len(nodes)
                url = doc.metadata.get("url", "")
                
                # Update article_records
                self.article_records[art_id] = {
                    "article_id": art_id,
                    "title": title,
                    "url": url,
                    "page_id": doc.metadata.get("page_id", ""),
                    "revision_id": doc.metadata.get("revision_id", ""),
                    "content_hash": doc.metadata.get("content_hash", ""),
                    "char_count": char_count,
                    "token_count": token_count,
                    "chunks_count": chunks_count,
                    "raw_text": doc.text,
                    "status": "indexed",
                    "last_error": None,
                    "loaded_at": time.time(),
                    "last_updated": time.time(),
                    "type": "wikipedia",
                    "is_active": True
                }

                meta_item = {
                    "article_id": art_id,
                    "title": title,
                    "url": url,
                    "char_count": char_count,
                    "token_count": token_count,
                    "chunks_count": chunks_count,
                    "type": "wikipedia",
                    "status": "indexed"
                }
                new_metas.append(meta_item)

                # Sync to history
                self._sync_history_record(title, url, char_count, chunks_count, is_active=True)

            if not new_chunks:
                return False, "Articles produced no usable text chunks.", status_map

            # Embed chunks using persistent SQLite cache & batching
            if progress_cb:
                progress_cb("Embedding", f"Computing dense embeddings for {len(new_chunks)} chunks...", 0.7)
            
            new_chunks, hits, computed = embed_nodes_batch(new_chunks, batch_size=32)

            # Accumulate into active state
            if replace_existing:
                self.loaded_documents = new_docs
                self.chunk_nodes = new_chunks
                self.doc_titles = [d.metadata.get("title", "Article") for d in new_docs]
                self.doc_metadata_list = new_metas
            else:
                self.loaded_documents.extend(new_docs)
                self.chunk_nodes.extend(new_chunks)
                self.doc_titles.extend([d.metadata.get("title", "Article") for d in new_docs])
                self.doc_metadata_list.extend(new_metas)

            # Build index
            if progress_cb:
                progress_cb("Indexing", "Building Vector Space Index...", 0.9)

            self._rebuild_index_from_nodes()
            self._save_state()

            if progress_cb:
                progress_cb("Completed", f"Ready: {len(self.doc_titles)} articles indexed!", 1.0)

            msg = f"Successfully indexed {len(new_docs)} article(s). Total knowledge base: {len(self.doc_titles)} articles ({len(self.chunk_nodes)} chunks)."
            return True, msg, status_map

    def _sync_history_record(self, title: str, url: str, char_count: int, chunks_count: int, is_active: bool = True):
        for item in self.article_history:
            if item.get("title", "").strip().lower() == title.strip().lower():
                item["url"] = url or item.get("url", "")
                item["char_count"] = char_count
                item["chunks_count"] = chunks_count
                item["is_active"] = is_active
                item["last_accessed"] = time.time()
                return
        self.article_history.insert(0, {
            "title": title.strip(),
            "url": url,
            "char_count": char_count,
            "chunks_count": chunks_count,
            "type": "wikipedia",
            "loaded_at": time.time(),
            "last_accessed": time.time(),
            "is_active": is_active,
        })

    def reload_articles_transactional(
        self,
        article_titles: List[str],
        mode: str = "reload_selected",  # reload_selected, reload_all, refresh_wikipedia, reprocess_content
        task_id: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        Transactional Staging-and-Commit Article Reload.
        
        Guarantees:
        - Safe update: If an article refresh fails, its previous valid chunks and version are PRESERVED!
        - Unrelated articles: Never touches or corrupts unrelated articles or their vectors.
        - Idempotency: Multiple runs produce identical consistent state.
        - Supports:
          * reload_selected: re-fetches selected titles and rebuilds chunks/embeddings
          * reload_all: re-fetches all managed articles
          * refresh_wikipedia: re-fetches and only updates if content hash changed
          * reprocess_content: re-chunks/re-embeds from existing stored text (0 network calls)
        """
        clean_titles = [t.strip() for t in article_titles if t.strip()]
        if mode == "reload_all":
            clean_titles = list(set([rec.get("title", "") for rec in self.article_records.values()] + self.doc_titles))

        if not clean_titles:
            return False, "No articles selected to reload.", {}

        total = len(clean_titles)
        status_map: Dict[str, str] = {}
        updated_articles = 0
        failed_articles = 0

        logger.info("Starting transactional reload (mode=%s) for %d articles...", mode, total)

        for i, title in enumerate(clean_titles):
            ratio = (i / total)
            if task_id:
                task_manager.update_task(task_id, "Processing", ratio, current_item=title)

            clean_title_lower = title.strip().lower()
            existing_rec = self._find_record_by_title(title)
            article_id = existing_rec.get("article_id") if existing_rec else self._get_stable_article_id(title)

            # STAGE 1: Acquire text (Network or Stored)
            doc_to_process: Optional[Document] = None
            if mode == "reprocess_content":
                if task_id:
                    task_manager.update_task(task_id, "Reprocessing", ratio, current_item=f"Re-chunking {title}")
                if existing_rec and existing_rec.get("raw_text"):
                    doc_to_process = Document(
                        text=existing_rec["raw_text"],
                        metadata={
                            "title": existing_rec["title"],
                            "url": existing_rec.get("url", ""),
                            "type": "wikipedia",
                            "char_count": len(existing_rec["raw_text"]),
                            "page_id": existing_rec.get("page_id", ""),
                            "revision_id": existing_rec.get("revision_id", "")
                        }
                    )
                else:
                    # Fallback to fetch if raw_text wasn't stored
                    doc_to_process, fetch_msg = WikipediaLoader.load_single_article(title)
            else:
                # Network fetch
                if task_id:
                    task_manager.update_task(task_id, "Fetching", ratio, current_item=f"Downloading {title}")
                doc_to_process, fetch_msg = WikipediaLoader.load_single_article(title)

            if not doc_to_process or not doc_to_process.text.strip():
                # TRANSACTION FAILURE: Preserve previous version!
                failed_articles += 1
                err_msg = f"Failed to acquire content for '{title}'. Previous version preserved."
                status_map[title] = err_msg
                if existing_rec:
                    existing_rec["status"] = "stale"
                    existing_rec["last_error"] = "Content refresh failed"
                if task_id:
                    task_manager.update_task(task_id, "Error", ratio, failed_delta=1, error=err_msg)
                logger.warning(err_msg)
                continue

            # Check if unchanged for refresh_wikipedia
            new_hash = hashlib.sha256(doc_to_process.text.encode("utf-8")).hexdigest()[:32]
            if mode == "refresh_wikipedia" and existing_rec and existing_rec.get("content_hash") == new_hash:
                status_map[title] = "Up to date (content unchanged)"
                updated_articles += 1
                if task_id:
                    task_manager.update_task(task_id, "Verified", ratio, completed_delta=1)
                continue

            # STAGE 2: Chunking
            if task_id:
                task_manager.update_task(task_id, "Chunking", ratio + (0.5 / total), current_item=f"Chunking {title}")
            staged_nodes = self.chunker.process_document(doc_to_process)
            if not staged_nodes:
                failed_articles += 1
                err_msg = f"Chunking produced 0 chunks for '{title}'. Previous version preserved."
                status_map[title] = err_msg
                if task_id:
                    task_manager.update_task(task_id, "Error", ratio, failed_delta=1, error=err_msg)
                continue

            # STAGE 3: Embedding
            if task_id:
                task_manager.update_task(task_id, "Embedding", ratio + (0.8 / total), current_item=f"Embedding {title}")
            staged_nodes, hits, computed = embed_nodes_batch(staged_nodes, batch_size=32)

            # STAGE 4: COMMIT — Atomically replace old chunks with staged chunks
            with self._lock:
                # Remove obsolete chunks for this article only
                self.chunk_nodes = [
                    n for n in self.chunk_nodes
                    if (n.metadata.get("article_id") != article_id and
                        (n.metadata.get("doc_title") or n.metadata.get("title") or "").strip().lower() != clean_title_lower)
                ]
                # Insert validated replacement chunks
                self.chunk_nodes.extend(staged_nodes)

                # Update or insert article record
                char_count = len(doc_to_process.text)
                token_count = sum(n.metadata.get("token_count", 0) for n in staged_nodes)
                chunks_count = len(staged_nodes)
                
                self.article_records[article_id] = {
                    "article_id": article_id,
                    "title": doc_to_process.metadata.get("title", title),
                    "url": doc_to_process.metadata.get("url", ""),
                    "page_id": doc_to_process.metadata.get("page_id", ""),
                    "revision_id": doc_to_process.metadata.get("revision_id", ""),
                    "content_hash": new_hash,
                    "char_count": char_count,
                    "token_count": token_count,
                    "chunks_count": chunks_count,
                    "raw_text": doc_to_process.text,
                    "status": "indexed",
                    "last_error": None,
                    "loaded_at": existing_rec.get("loaded_at", time.time()) if existing_rec else time.time(),
                    "last_updated": time.time(),
                    "type": "wikipedia",
                    "is_active": True
                }

                # Ensure title in doc_titles
                clean_title = doc_to_process.metadata.get("title", title)
                if not any(t.strip().lower() == clean_title.strip().lower() for t in self.doc_titles):
                    self.doc_titles.append(clean_title)

                self._sync_history_record(clean_title, doc_to_process.metadata.get("url", ""), char_count, chunks_count, is_active=True)

            status_map[title] = f"Successfully reloaded ({chunks_count} chunks, {token_count} tokens)"
            updated_articles += 1
            if task_id:
                task_manager.update_task(task_id, "Committed", ratio + (1.0 / total), completed_delta=1)

        # STAGE 5: Rebuild index over combined chunks
        with self._lock:
            if task_id:
                task_manager.update_task(task_id, "Indexing", 0.95, current_item="Updating Vector Index")
            self._rebuild_index_from_nodes()
            self._reconcile_state()
            self._save_state()

        summary_msg = f"Reload complete: {updated_articles} updated, {failed_articles} preserved/failed."
        if task_id:
            task_manager.complete_task(task_id, summary_msg, success=(failed_articles == 0))

        return (failed_articles == 0 or updated_articles > 0), summary_msg, status_map

    def launch_async_reload(self, titles: List[str], mode: str = "reload_selected") -> str:
        """Launches transactional reload in a background worker thread."""
        task_id = task_manager.create_task(f"{mode.replace('_', ' ').title()}", len(titles))
        
        def _worker():
            try:
                self.reload_articles_transactional(titles, mode=mode, task_id=task_id)
            except Exception as e:
                logger.error("Async reload worker encountered fatal exception: %s", e)
                task_manager.complete_task(task_id, f"Fatal error: {str(e)}", success=False)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return task_id

    def remove_article(self, title: str, delete_from_history: bool = False) -> Tuple[bool, str]:
        """Removes an article from the active vector index, preserving other articles."""
        clean_title = title.strip().lower()
        
        with self._lock:
            # 1. Filter out chunks belonging to this article
            self.chunk_nodes = [
                n for n in self.chunk_nodes
                if (n.metadata.get("title") or n.metadata.get("doc_title") or "").strip().lower() != clean_title
            ]
            self.doc_titles = [t for t in self.doc_titles if t.strip().lower() != clean_title]
            self.doc_metadata_list = [m for m in self.doc_metadata_list if m.get("title", "").strip().lower() != clean_title]
            self.loaded_documents = [d for d in self.loaded_documents if d.metadata.get("title", "").strip().lower() != clean_title]

            # 2. Update article_records status
            target_rec = self._find_record_by_title(title)
            if target_rec:
                target_rec["is_active"] = False
                target_rec["status"] = "saved"

            # 3. Re-index remaining chunks
            self._rebuild_index_from_nodes()

            # 4. History
            if delete_from_history:
                self.article_history = [h for h in self.article_history if h.get("title", "").strip().lower() != clean_title]
                if target_rec:
                    art_id = target_rec.get("article_id")
                    if art_id in self.article_records:
                        del self.article_records[art_id]
            else:
                for h in self.article_history:
                    if h.get("title", "").strip().lower() == clean_title:
                        h["is_active"] = False

            self._save_state()

        return True, f"Successfully removed '{title}' from active knowledge base."

    def query_rag(
        self,
        question: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        article_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes the full 6-stage RAG workflow with detailed instrumentation and
        bulletproof error recovery. Never raises unhandled exceptions.
        """
        start_time = time.time()
        stages = []

        # Stage 1: QUERY
        clean_q = question.strip()
        if not clean_q:
            return {"success": False, "error": "Query cannot be empty.", "stages": []}

        stages.append({
            "stage": "QUERY",
            "title": "Query Received",
            "description": f"Target question: '{clean_q[:60]}...'",
            "time_ms": int((time.time() - start_time) * 1000)
        })

        # Check knowledge base
        if not self.index or not self.chunk_nodes:
            return {
                "success": False,
                "error": "No knowledge base loaded yet. Please load Wikipedia articles first.",
                "stages": stages,
                "evidences": [],
                "citations": {"total_retrieved": 0, "total_cited": 0, "cited_keys": [], "cards": []}
            }

        # Stage 2: UNDERSTAND
        t_under = time.time()
        active_scope_desc = f"Scope: {len(article_filter)} selected articles" if article_filter else f"Scope: All {len(self.doc_titles)} articles"
        stages.append({
            "stage": "UNDERSTAND",
            "title": "Semantic Analysis",
            "description": f"{active_scope_desc} · Model: {settings.embedding_model_name.split('/')[-1]}",
            "time_ms": int((time.time() - t_under) * 1000)
        })

        # Stage 3: RETRIEVE
        t_ret = time.time()
        try:
            retriever = RAGRetriever(self.index)
            evidences = retriever.retrieve(
                query=clean_q,
                top_k=top_k or settings.top_k,
                similarity_threshold=similarity_threshold if similarity_threshold is not None else settings.similarity_threshold,
                article_filter=article_filter,
                max_token_budget=settings.context_token_budget
            )
            self.last_retrieved = evidences
            self.last_query = clean_q
        except Exception as e:
            logger.error("Retrieval stage encountered error: %s", e)
            evidences = []
            self.last_retrieved = []

        stages.append({
            "stage": "RETRIEVE",
            "title": "Vector Space Search",
            "description": f"Retrieved {len(evidences)} passages from {len(self.chunk_nodes)} indexed chunks",
            "time_ms": int((time.time() - t_ret) * 1000)
        })

        # Stage 4: RERANK / DEDUPLICATE
        t_rank = time.time()
        top_score = evidences[0].similarity_score if evidences else 0.0
        stages.append({
            "stage": "RERANK",
            "title": "Evidence Filtering & Ranking",
            "description": f"Top similarity score: {top_score:.4f}" if evidences else "No matches above relevance threshold",
            "time_ms": int((time.time() - t_rank) * 1000)
        })

        # Stage 5: GENERATE
        t_gen = time.time()
        try:
            raw_answer = self.generator.generate(clean_q, evidences)
        except Exception as e:
            logger.error("Generation error caught gracefully: %s", e)
            raw_answer = (
                f"⚠️ **AI Answer Generation Unavailable**\n\n"
                f"**Diagnostics:** An error occurred during synthesis ({str(e)[:120]}).\n\n"
                f"*{len(evidences)} relevant knowledge passages were successfully retrieved and are available in the Evidence Panel.*"
            )

        stages.append({
            "stage": "GENERATE",
            "title": "Grounded AI Synthesis",
            "description": f"Model: {settings.llm_model} · {len(raw_answer)} chars",
            "time_ms": int((time.time() - t_gen) * 1000)
        })

        # Stage 6: CITE
        t_cite = time.time()
        citation_data = CitationManager.process_citations(raw_answer, evidences)
        stages.append({
            "stage": "CITE",
            "title": "Citation Linking",
            "description": f"Linked {citation_data['total_cited']} direct citations across {citation_data['total_retrieved']} evidence sources",
            "time_ms": int((time.time() - t_cite) * 1000)
        })

        total_elapsed = round(time.time() - start_time, 2)

        chat_entry = {
            "query": clean_q,
            "answer": raw_answer,
            "citations": citation_data,
            "evidences": [e.to_dict() for e in evidences],
            "stages": stages,
            "elapsed_seconds": total_elapsed,
            "timestamp": time.time()
        }
        self.chat_history.append(chat_entry)

        return {
            "success": True,
            "query": clean_q,
            "answer": raw_answer,
            "citations": citation_data,
            "evidences": [e.to_dict() for e in evidences],
            "stages": stages,
            "elapsed_seconds": total_elapsed
        }

    def get_knowledge_graph(self) -> Dict[str, Any]:
        """Produces 3D spatial graph representation."""
        retrieved_ids = [e.chunk_id for e in self.last_retrieved]
        return KnowledgeGraphBuilder.build_graph(
            documents_meta=self.doc_metadata_list,
            chunk_nodes=self.chunk_nodes,
            active_query=self.last_query,
            retrieved_chunk_ids=retrieved_ids
        )

    def clear_cache(self) -> Tuple[bool, str]:
        with self._lock:
            count = 0
            try:
                for pkl in CACHE_DIR.glob("*.pkl"):
                    pkl.unlink()
                    count += 1
                self.loaded_documents = []
                self.chunk_nodes = []
                self.doc_titles = []
                self.doc_metadata_list = []
                self.index = None
                self.last_retrieved = []
                self.last_query = None
                return True, f"Successfully cleared {count} cached index file(s) and reset knowledge base."
            except Exception as e:
                return False, f"Error clearing cache: {e}"

    def clear_chat(self):
        self.chat_history = []
        self.last_retrieved = []
        self.last_query = None

# Global RAG Engine singleton
rag_engine = RAGEngine()
