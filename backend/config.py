import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env file from project root
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

CACHE_DIR = ROOT_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

MODEL_CACHE_DIR = ROOT_DIR / "model_cache"
MODEL_CACHE_DIR.mkdir(exist_ok=True)

_cached_device = None

def detect_device() -> str:
    global _cached_device
    if _cached_device is not None:
        return _cached_device
    try:
        import torch
        if torch.cuda.is_available():
            _cached_device = "cuda"
            return "cuda"
    except Exception:
        pass
    _cached_device = "cpu"
    return "cpu"

class AppConfig(BaseModel):
    # LLM
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "gemini-3.5-flash")
    temperature: float = float(os.getenv("TEMPERATURE", "0.3"))
    max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))
    timeout_seconds: int = int(os.getenv("TIMEOUT_SECONDS", "30"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    
    # RAG / Retrieval
    top_k: int = int(os.getenv("TOP_K", "5"))
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.20"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "75"))
    context_token_budget: int = int(os.getenv("CONTEXT_TOKEN_BUDGET", "3000"))
    
    # Embeddings
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-MiniLM-L3-v2")
    device: str = Field(default_factory=detect_device)
    
    # Server
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))

# Global singleton settings
settings = AppConfig()

def update_settings(**kwargs):
    global settings
    curr_data = settings.model_dump()
    for k, v in kwargs.items():
        if v is not None and k in curr_data:
            curr_data[k] = v
    settings = AppConfig(**curr_data)
    
    # Also save to .env if gemini_api_key was updated
    if "gemini_api_key" in kwargs and kwargs["gemini_api_key"]:
        try:
            env_path = ROOT_DIR / ".env"
            lines = []
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            
            key_set = False
            new_lines = []
            for line in lines:
                if line.startswith("GEMINI_API_KEY="):
                    new_lines.append(f"GEMINI_API_KEY={kwargs['gemini_api_key']}\n")
                    key_set = True
                else:
                    new_lines.append(line)
            if not key_set:
                new_lines.append(f"GEMINI_API_KEY={kwargs['gemini_api_key']}\n")
            
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception:
            pass
    return settings
