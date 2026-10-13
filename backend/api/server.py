import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.config import settings
from backend.api.routes import router
from backend.rag.embeddings import get_embedding_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("rag_api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    logger.info("Initializing RAG backend services...")
    # Preload embedding model in a background thread so server starts accepting connections immediately
    def _preload():
        try:
            get_embedding_model()
            logger.info("Embedding model pre-loaded and ready in background.")
        except Exception as e:
            logger.error("Embedding model preloading error: %s", e)
    
    t = threading.Thread(target=_preload, daemon=True)
    t.start()
    yield
    logger.info("Shutting down RAG backend services.")

app = FastAPI(
    title="RAG 3D Research Universe API",
    description="Intelligent Retrieval-Augmented Generation Platform with 3D Knowledge Space",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Mount frontend dist static files if built
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.server:app", host=settings.api_host, port=settings.api_port, reload=True)
