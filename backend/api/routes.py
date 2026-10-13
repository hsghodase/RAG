import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.config import settings, update_settings, CACHE_DIR
from backend.rag.engine import rag_engine, task_manager
from backend.rag.embeddings import embedding_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Request Models
class ConfigUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    top_k: Optional[int] = None
    similarity_threshold: Optional[float] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    context_token_budget: Optional[int] = None

class LoadArticlesRequest(BaseModel):
    articles: List[str] = Field(default_factory=list)
    topic_name: Optional[str] = None

class ReloadArticlesRequest(BaseModel):
    articles: List[str] = Field(default_factory=list)
    mode: str = "reload_selected"  # reload_selected, reload_all, refresh_wikipedia, reprocess_content
    async_mode: bool = True

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = None
    similarity_threshold: Optional[float] = None
    article_filter: Optional[List[str]] = None

class RemoveArticleRequest(BaseModel):
    title: str
    delete_from_history: Optional[bool] = False

# Quick start topics mapping
QUICK_TOPICS = {
    "AI": ["Artificial Intelligence", "Machine Learning", "Deep Learning"],
    "Science": ["Physics", "Chemistry", "Biology"],
    "Technology": ["Cloud Computing", "Quantum Computing", "Cybersecurity"],
    "Economics": ["Economics", "Inflation", "Monetary Policy"],
    "History": ["Renaissance", "Industrial Revolution", "Space Exploration"]
}

@router.get("/health")
def get_health_status():
    """Backend health check endpoint with diagnostics and component statuses."""
    is_key_present = bool(settings.gemini_api_key and len(settings.gemini_api_key) > 5)
    return {
        "status": "healthy",
        "online": True,
        "database": "ready",
        "vector_index_ready": rag_engine.index is not None,
        "active_articles": len(rag_engine.doc_titles),
        "total_chunks": len(rag_engine.chunk_nodes),
        "cached_embeddings_count": embedding_cache.count(),
        "llm_configured": is_key_present,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model_name,
        "device": settings.device
    }

@router.get("/status")
def get_system_status():
    cache_files = list(CACHE_DIR.glob("*.pkl"))
    return {
        "online": True,
        "device": settings.device,
        "embedding_model": settings.embedding_model_name,
        "llm_model": settings.llm_model,
        "has_api_key": bool(settings.gemini_api_key and len(settings.gemini_api_key) > 5),
        "documents_loaded": len(rag_engine.doc_titles),
        "total_chunks": len(rag_engine.chunk_nodes),
        "cached_indexes": len(cache_files),
        "cached_embeddings": embedding_cache.count(),
        "chat_turns": len(rag_engine.chat_history),
    }

@router.get("/config")
def get_configuration():
    return {
        "llm_model": settings.llm_model,
        "temperature": settings.temperature,
        "max_output_tokens": settings.max_output_tokens,
        "top_k": settings.top_k,
        "similarity_threshold": settings.similarity_threshold,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "context_token_budget": settings.context_token_budget,
        "device": settings.device,
        "embedding_model": settings.embedding_model_name,
        "has_api_key": bool(settings.gemini_api_key and len(settings.gemini_api_key) > 5),
        "api_key_masked": (settings.gemini_api_key[:6] + "..." + settings.gemini_api_key[-4:]) if len(settings.gemini_api_key) > 10 else ""
    }

@router.post("/config")
def update_configuration(req: ConfigUpdateRequest):
    update_data = req.model_dump(exclude_unset=True)
    updated = update_settings(**update_data)
    # Refresh generator client
    rag_engine.generator = rag_engine.generator.__class__(
        api_key=updated.gemini_api_key,
        model_name=updated.llm_model
    )
    return {
        "status": "success",
        "message": "Configuration updated successfully",
        "has_api_key": bool(updated.gemini_api_key and len(updated.gemini_api_key) > 5),
        "llm_model": updated.llm_model,
        "top_k": updated.top_k,
        "chunk_size": updated.chunk_size
    }

@router.post("/config/test-connection")
def test_llm_connection():
    """Tests live LLM connectivity with measured latency and active model info."""
    ok, msg, info = rag_engine.generator.test_connection()
    return {
        "success": ok,
        "message": msg,
        "info": info
    }

@router.get("/topics")
def get_quick_topics():
    return QUICK_TOPICS

@router.post("/articles/load")
def load_articles(req: LoadArticlesRequest):
    if not req.articles and req.topic_name in QUICK_TOPICS:
        target_articles = QUICK_TOPICS[req.topic_name]
    else:
        target_articles = req.articles

    if not target_articles:
        raise HTTPException(status_code=400, detail="No article titles specified.")

    try:
        success, message, status_map = rag_engine.ingest_wikipedia_articles(target_articles)
        if not success:
            raise HTTPException(status_code=400, detail={"message": message, "status_map": status_map})

        payload = rag_engine.get_articles_payload()
        return {
            "success": True,
            "message": message,
            "articles": payload["articles"],
            "total_chunks": payload["total_chunks"],
            "history": payload["history"],
            "status_map": status_map
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error loading articles: %s", e)
        raise HTTPException(status_code=500, detail=f"Article ingestion error: {str(e)}")

@router.post("/articles/reload")
def reload_articles(req: ReloadArticlesRequest):
    """
    Performs safe transactional reload, refresh from Wikipedia, or content reprocessing.
    Supports asynchronous background execution with real-time polling.
    """
    targets = req.articles
    if req.mode == "reload_all":
        targets = [rec.get("title", "") for rec in rag_engine.article_records.values()] or rag_engine.doc_titles

    if not targets and req.mode != "reload_all":
        raise HTTPException(status_code=400, detail="No articles selected to reload.")

    if req.async_mode:
        task_id = rag_engine.launch_async_reload(targets, mode=req.mode)
        return {
            "success": True,
            "task_id": task_id,
            "mode": req.mode,
            "message": f"Article operation '{req.mode}' queued in background for {len(targets)} article(s)."
        }
    else:
        success, message, status_map = rag_engine.reload_articles_transactional(targets, mode=req.mode)
        payload = rag_engine.get_articles_payload()
        return {
            "success": success,
            "message": message,
            "status_map": status_map,
            "articles": payload["articles"],
            "total_chunks": payload["total_chunks"]
        }

@router.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    """Poll progress for an ongoing ingestion / reload background job."""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task ID not found.")
    return task

@router.get("/articles")
def list_articles():
    return rag_engine.get_articles_payload()

@router.post("/articles/remove")
def remove_article(req: RemoveArticleRequest):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Article title is required.")
    
    try:
        success, msg = rag_engine.remove_article(req.title, req.delete_from_history or False)
        payload = rag_engine.get_articles_payload()
        return {
            "success": success,
            "message": msg,
            "articles": payload["articles"],
            "total_chunks": payload["total_chunks"],
            "history": payload["history"]
        }
    except Exception as e:
        logger.error("Error removing article: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to remove article: {str(e)}")

@router.post("/query")
def execute_query(req: QueryRequest):
    """
    Executes grounded RAG research query.
    Never throws HTTP 500: catches all edge cases and preserves retrieved evidence.
    """
    clean_q = req.query.strip()
    if not clean_q:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    try:
        result = rag_engine.query_rag(
            question=clean_q,
            top_k=req.top_k,
            similarity_threshold=req.similarity_threshold,
            article_filter=req.article_filter
        )
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Query failed."))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in execute_query: %s", e, exc_info=True)
        # Even if unexpected error occurs, return 400 with actionable detail rather than 500
        raise HTTPException(
            status_code=400,
            detail=f"Query execution could not be completed: {str(e)}. Please check your knowledge base or settings."
        )

@router.post("/query/stream")
def execute_query_stream(req: QueryRequest):
    """Streams generated answer chunks as SSE (Server-Sent Events)."""
    clean_q = req.query.strip()
    if not clean_q:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not rag_engine.index or not rag_engine.chunk_nodes:
        raise HTTPException(status_code=400, detail="No knowledge base loaded yet.")

    # 1. Retrieve evidence
    from backend.rag.retrieval import RAGRetriever
    retriever = RAGRetriever(rag_engine.index)
    evidences = retriever.retrieve(
        query=clean_q,
        top_k=req.top_k or settings.top_k,
        similarity_threshold=req.similarity_threshold or settings.similarity_threshold,
        article_filter=req.article_filter
    )
    rag_engine.last_retrieved = evidences
    rag_engine.last_query = clean_q

    def _event_generator():
        # First send evidences
        yield f"data: {json.dumps({'type': 'evidence', 'evidences': [e.to_dict() for e in evidences]})}\n\n"
        
        # Then stream answer tokens
        full_answer = []
        for token in rag_engine.generator.generate_stream(clean_q, evidences):
            full_answer.append(token)
            yield f"data: {json.dumps({'type': 'chunk', 'text': token})}\n\n"
        
        # Finally citations
        ans_text = "".join(full_answer)
        from backend.rag.citations import CitationManager
        citations = CitationManager.process_citations(ans_text, evidences)
        yield f"data: {json.dumps({'type': 'done', 'citations': citations})}\n\n"

    return StreamingResponse(_event_generator(), media_type="text/event-stream")

@router.get("/graph")
def get_graph():
    return rag_engine.get_knowledge_graph()

@router.get("/chat/history")
def get_chat_history():
    return rag_engine.chat_history

@router.post("/chat/clear")
def clear_chat():
    rag_engine.clear_chat()
    return {"status": "success", "message": "Chat history cleared."}

@router.post("/cache/clear")
def clear_cache():
    success, msg = rag_engine.clear_cache()
    return {"status": "success" if success else "error", "message": msg}
