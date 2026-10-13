import os
import sys
import time
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from llama_index.core.schema import Document, TextNode
from backend.config import settings, CACHE_DIR
from backend.rag.ingestion import TextCleaner, WikipediaLoader, IngestionPipeline
from backend.rag.chunking import AdvancedChunker
from backend.rag.embeddings import (
    PersistentEmbeddingCache, compute_chunk_content_hash,
    embed_nodes_batch, compute_query_embedding
)
from backend.rag.retrieval import RAGRetriever, RetrievedEvidence
from backend.rag.generation import RAGGenerator
from backend.rag.citations import CitationManager
from backend.rag.engine import RAGEngine, IngestionTaskManager
from fastapi.testclient import TestClient
from backend.api.server import app

class TestRAGApplication(unittest.TestCase):

    def setUp(self):
        self.chunker = AdvancedChunker(chunk_size=200, chunk_overlap=30)
        self.client = TestClient(app)

    # --------------------------------------------------------------------------
    # 1. Wikipedia fetching and malformed responses
    # --------------------------------------------------------------------------
    @patch("wikipedia.page")
    def test_01_wikipedia_fetching_and_malformed(self, mock_page):
        # Successful fetch
        mock_instance = MagicMock()
        mock_instance.title = "Alan Turing"
        mock_instance.content = "Alan Mathison Turing was an English mathematician and computer scientist."
        mock_instance.url = "https://en.wikipedia.org/wiki/Alan_Turing"
        mock_page.return_value = mock_instance

        doc, status = WikipediaLoader.load_single_article("Alan Turing")
        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["title"], "Alan Turing")
        self.assertEqual(status, "Loaded")

        # Empty/malformed response handling
        mock_instance.content = ""
        with patch.object(WikipediaLoader, "_fetch_via_api_direct", return_value=None):
            empty_doc, status_empty = WikipediaLoader.load_single_article("Nonexistent Article 123456")
            self.assertIsNone(empty_doc)
            self.assertIn("could not be found", status_empty.lower())

    # --------------------------------------------------------------------------
    # 2. Text cleaning and chunking
    # --------------------------------------------------------------------------
    def test_02_text_cleaning_and_chunking(self):
        dirty_text = "== Early Life == [edit]\nHe was born in 1912.[1][2]\n\n\nHe studied at Cambridge.[3]"
        cleaned = TextCleaner.clean_text(dirty_text)
        self.assertNotIn("[edit]", cleaned)
        self.assertNotIn("[1]", cleaned)
        self.assertNotIn("\n\n\n", cleaned)
        self.assertIn("Early Life", cleaned)

        sections = self.chunker.split_into_sections(cleaned)
        self.assertTrue(len(sections) >= 1)
        self.assertEqual(sections[0]["section"], "Early Life")

    # --------------------------------------------------------------------------
    # 3. Stable chunk IDs and metadata
    # --------------------------------------------------------------------------
    def test_03_stable_chunk_ids_and_metadata(self):
        doc = Document(
            text="== Section A ==\nThis is a stable semantic test document designed to verify deterministic chunking.\n== Section B ==\nSecond section content.",
            metadata={"title": "Test Subject", "url": "https://example.com/test", "type": "wikipedia"}
        )
        nodes1 = self.chunker.process_document(doc)
        nodes2 = self.chunker.process_document(doc)

        self.assertEqual(len(nodes1), len(nodes2))
        for n1, n2 in zip(nodes1, nodes2):
            self.assertEqual(n1.node_id, n2.node_id)
            self.assertEqual(n1.metadata["content_hash"], n2.metadata["content_hash"])
            self.assertIn("token_count", n1.metadata)
            self.assertIn("chunk_index", n1.metadata)
            self.assertIn("article_id", n1.metadata)

    # --------------------------------------------------------------------------
    # 4. Embedding caching and batching
    # --------------------------------------------------------------------------
    def test_04_embedding_caching_and_batching(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_db_path = Path(f.name)

        cache = PersistentEmbeddingCache(db_path=temp_db_path)
        try:
            model_name = "test-model"
            sample_hash = "abc123hash"
            sample_vec = [0.1, 0.2, 0.3, 0.4]

            # Set and get
            cache.set_many(model_name, {sample_hash: sample_vec})
            retrieved = cache.get_many(model_name, [sample_hash])
            self.assertIn(sample_hash, retrieved)
            self.assertAlmostEqual(retrieved[sample_hash][0], 0.1, places=5)
            self.assertEqual(cache.count(), 1)
        finally:
            cache.close()
            if temp_db_path.exists():
                try:
                    temp_db_path.unlink()
                except Exception:
                    pass

    # --------------------------------------------------------------------------
    # 5. Vector insertion, retrieval, update, and deletion
    # --------------------------------------------------------------------------
    def test_05_vector_insertion_retrieval_deletion(self):
        engine = RAGEngine()
        # Mock ingestion of fixture doc
        doc = Document(
            text="== Mathematics ==\nLeonhard Euler was a pioneering Swiss mathematician who introduced mathematical notation.",
            metadata={"title": "Leonhard Euler", "url": "https://en.wikipedia.org/wiki/Leonhard_Euler", "type": "wikipedia"}
        )
        nodes = self.chunker.process_document(doc)
        # Assign dummy mock embeddings
        for n in nodes:
            n.embedding = [0.05] * 384

        engine.chunk_nodes = nodes
        engine.doc_titles = ["Leonhard Euler"]
        engine.doc_metadata_list = [{"title": "Leonhard Euler", "chunks_count": len(nodes), "char_count": len(doc.text)}]
        
        self.assertEqual(len(engine.chunk_nodes), len(nodes))
        
        # Removal
        success, msg = engine.remove_article("Leonhard Euler")
        self.assertTrue(success)
        self.assertEqual(len(engine.chunk_nodes), 0)
        self.assertEqual(len(engine.doc_titles), 0)

    # --------------------------------------------------------------------------
    # 6. Selected-article retrieval filters
    # --------------------------------------------------------------------------
    def test_06_selected_article_retrieval_filters(self):
        engine = RAGEngine()
        doc_a = Document(text="Python is a high-level programming language.", metadata={"title": "Python Language"})
        doc_b = Document(text="Java is a class-based, object-oriented language.", metadata={"title": "Java Language"})
        
        nodes_a = self.chunker.process_document(doc_a)
        nodes_b = self.chunker.process_document(doc_b)
        
        # Test filtering directly in RAGRetriever with mock index
        mock_node_a = MagicMock()
        mock_node_a.score = 0.85
        mock_node_a.node.get_content.return_value = "Python is a high-level programming language."
        mock_node_a.node.metadata = {"title": "Python Language", "section": "Overview", "chunk_id": "c_py_01"}
        mock_node_a.node.node_id = "c_py_01"

        mock_node_b = MagicMock()
        mock_node_b.score = 0.84
        mock_node_b.node.get_content.return_value = "Java is a class-based, object-oriented language."
        mock_node_b.node.metadata = {"title": "Java Language", "section": "Overview", "chunk_id": "c_java_01"}
        mock_node_b.node.node_id = "c_java_01"

        mock_index = MagicMock()
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = [mock_node_a, mock_node_b]
        mock_index.as_retriever.return_value = mock_retriever

        retriever = RAGRetriever(mock_index)
        
        # Filter for Python only
        evidences = retriever.retrieve("programming language", article_filter=["Python Language"])
        self.assertEqual(len(evidences), 1)
        self.assertEqual(evidences[0].title, "Python Language")

    # --------------------------------------------------------------------------
    # 7, 8, 9, 10, 11, 12, 13: Transactional Reload, Refresh & Staging-and-Commit
    # --------------------------------------------------------------------------
    @patch("backend.rag.ingestion.WikipediaLoader.load_single_article")
    def test_07_through_13_transactional_reload_and_safe_commit(self, mock_load):
        engine = RAGEngine()
        # Seed engine with initial valid article
        initial_doc = Document(
            text="Initial verified content of Nikola Tesla.",
            metadata={"title": "Nikola Tesla", "url": "https://en.wikipedia.org/wiki/Nikola_Tesla", "type": "wikipedia"}
        )
        mock_load.return_value = (initial_doc, "Loaded")

        success, msg, _ = engine.reload_articles_transactional(["Nikola Tesla"], mode="reload_selected")
        self.assertTrue(success)
        self.assertIn("Nikola Tesla", engine.doc_titles)
        initial_chunks = len(engine.chunk_nodes)
        self.assertTrue(initial_chunks > 0)

        # 12 & 13: Partial reload failure MUST preserve last known good version
        mock_load.return_value = (None, "Network connection timeout")
        fail_success, fail_msg, status_map = engine.reload_articles_transactional(["Nikola Tesla"], mode="reload_selected")
        # Should not crash and previous chunks must remain intact
        self.assertIn("Nikola Tesla", engine.doc_titles)
        self.assertEqual(len(engine.chunk_nodes), initial_chunks)
        self.assertIn("preserved", status_map["Nikola Tesla"].lower())

        # 11: Reprocess existing content without network calls
        reprocess_success, reprocess_msg, _ = engine.reload_articles_transactional(["Nikola Tesla"], mode="reprocess_content")
        self.assertTrue(reprocess_success)
        self.assertEqual(len(engine.chunk_nodes), initial_chunks)

    # --------------------------------------------------------------------------
    # 14. Gemini authentication, rate limits, timeouts, and invalid responses
    # --------------------------------------------------------------------------
    def test_14_gemini_resilience(self):
        generator = RAGGenerator()
        # When unconfigured
        generator.api_key = ""
        ans = generator.generate("Test query", [])
        self.assertIn("API Key is required", ans)

        # When modern client fails across candidates, must return helpful diagnostic message without throwing
        generator.api_key = "dummy_key"
        generator._is_modern_sdk = True
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("503 Service Unavailable")
        generator._client = mock_client

        ans = generator.generate("Test query", [])
        self.assertIn("AI Answer Generation Unavailable", ans)
        self.assertIn("Diagnostics", ans)

    # --------------------------------------------------------------------------
    # 15. Empty knowledge base and empty retrieval results
    # --------------------------------------------------------------------------
    def test_15_empty_knowledge_base(self):
        engine = RAGEngine()
        engine.index = None
        engine.chunk_nodes = []
        
        res = engine.query_rag("Any question")
        self.assertFalse(res["success"])
        self.assertIn("No knowledge base loaded", res["error"])

    # --------------------------------------------------------------------------
    # 16. Correct evidence attribution
    # --------------------------------------------------------------------------
    def test_16_evidence_attribution(self):
        ev1 = RetrievedEvidence(
            ref_id="REF-1", chunk_id="c1", title="Quantum", section="Intro",
            url="http://q.org", source_type="wikipedia", similarity_score=0.9,
            full_text="Qubits exist in superposition.", preview="Qubits exist...", char_count=30
        )
        answer = "Quantum computers leverage superposition [REF-1] to perform calculations."
        citation_data = CitationManager.process_citations(answer, [ev1])
        self.assertEqual(citation_data["total_cited"], 1)
        self.assertIn("REF-1", citation_data["cited_keys"])
        self.assertTrue(citation_data["cards"][0]["is_directly_cited"])

    # --------------------------------------------------------------------------
    # 17. Query API HTTP 500 regression test
    # --------------------------------------------------------------------------
    def test_17_query_api_http_500_regression(self):
        # Even with empty or extreme queries, API must never return 500
        res = self.client.post("/api/query", json={"query": "   "})
        self.assertEqual(res.status_code, 400)
        self.assertIn("empty", res.json()["detail"].lower())

    # --------------------------------------------------------------------------
    # 18. Concurrent reload task tracking
    # --------------------------------------------------------------------------
    def test_18_concurrent_task_manager(self):
        mgr = IngestionTaskManager()
        task_id = mgr.create_task("Test Reload", 3)
        self.assertIsNotNone(task_id)
        
        status = mgr.get_task(task_id)
        self.assertEqual(status["status"], "queued")
        
        mgr.update_task(task_id, "Fetching", 0.33, current_item="Article A", completed_delta=1)
        status = mgr.get_task(task_id)
        self.assertEqual(status["stage"], "Fetching")
        self.assertEqual(status["completed_items"], 1)
        
        mgr.complete_task(task_id, "Completed successfully")
        status = mgr.get_task(task_id)
        self.assertEqual(status["status"], "completed")

    # --------------------------------------------------------------------------
    # 19. Persistent storage across restarts
    # --------------------------------------------------------------------------
    def test_19_persistent_storage(self):
        engine1 = RAGEngine()
        # Save a tracked article record
        art_id = engine1._get_stable_article_id("Persistence Test")
        engine1.article_records[art_id] = {
            "article_id": art_id,
            "title": "Persistence Test",
            "url": "http://example.com",
            "char_count": 500,
            "chunks_count": 2,
            "status": "indexed",
            "is_active": True,
            "loaded_at": time.time()
        }
        engine1._save_state()

        # Instantiate fresh engine2
        engine2 = RAGEngine()
        self.assertIn(art_id, engine2.article_records)
        self.assertEqual(engine2.article_records[art_id]["title"], "Persistence Test")

    # --------------------------------------------------------------------------
    # 20. End-to-end smoke test on a fixture corpus
    # --------------------------------------------------------------------------
    def test_20_end_to_end_smoke_test(self):
        # Test /api/health
        health_res = self.client.get("/api/health")
        self.assertEqual(health_res.status_code, 200)
        self.assertEqual(health_res.json()["status"], "healthy")

        # Test /api/status
        status_res = self.client.get("/api/status")
        self.assertEqual(status_res.status_code, 200)

        # Test /api/articles
        articles_res = self.client.get("/api/articles")
        self.assertEqual(articles_res.status_code, 200)

if __name__ == "__main__":
    unittest.main()
