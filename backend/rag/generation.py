import time
import random
import logging
from typing import List, Dict, Any, Optional, Iterator, Tuple
from backend.config import settings
from backend.rag.retrieval import RetrievedEvidence

logger = logging.getLogger(__name__)

RAG_SYSTEM_INSTRUCTION = """You are an elite AI research scientist and factual knowledge engine.
Your purpose is to answer the user's inquiry with utmost precision, strictly anchored in the retrieved evidence passages provided below.

CORE OPERATIONAL PROTOCOLS:
1. FACTUAL GROUNDING: Rely strictly on the facts, findings, and figures provided in the retrieved evidence. Never fabricate, extrapolate, or introduce hallucinated claims.
2. CITATIONS: Every factual assertion, quantitative data point, or non-obvious statement MUST be explicitly cited immediately at the end of the sentence using square bracket notation, e.g., [REF-1] or [REF-1, REF-2].
3. UNCERTAINTY & INCOMPLETE CONTEXT: If the retrieved passages do not contain adequate information to answer all or part of the question, explicitly state: "The loaded knowledge base does not contain sufficient evidence to answer [specific detail]."
4. RESPONSE ARCHITECTURE: Structure your response cleanly in Markdown:
   - **Executive Summary / Direct Answer**: Direct, high-level synthesis with citations.
   - **Key Findings & Evidence**: Bulleted breakdown of essential facts, mechanics, or historical developments.
   - **Limitations / Context Bounds**: (If relevant, mention what is not covered).
   - **Suggested Inquiries**: 2-3 relevant follow-up questions the user might ask based on this knowledge.
"""

MODERN_CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
]

class RAGGenerator:
    """
    Handles LLM grounding using the modern Google GenAI SDK with bounded retries,
    exponential backoff, model fallback, and robust error recovery.
    """
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.llm_model
        self._client = None
        self._is_modern_sdk = False
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            return
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            self._is_modern_sdk = True
            logger.info("Initialized Google GenAI SDK client.")
        except Exception as e:
            logger.warning("Modern google.genai initialization failed (%s), trying fallback...", e)
            try:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=self.api_key)
                self._legacy_genai = legacy_genai
                self._is_modern_sdk = False
            except Exception as e2:
                logger.error("All Gemini SDK initializations failed: %s", e2)
                self._client = None

    def is_configured(self) -> bool:
        return bool(self.api_key and (self._client is not None or hasattr(self, '_legacy_genai')))

    def test_connection(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Actively validates API connectivity, model availability, and measures ping latency.
        Never exposes raw API keys.
        """
        if not self.api_key:
            return False, "No Gemini API key configured.", {}

        self._init_client()
        if not self.is_configured():
            return False, "Failed to initialize Gemini SDK client.", {}

        t0 = time.time()
        test_models = [self.model_name] + [m for m in MODERN_CANDIDATE_MODELS if m != self.model_name]

        last_error = ""
        for model_id in test_models:
            try:
                if self._is_modern_sdk and self._client:
                    from google.genai import types
                    resp = self._client.models.generate_content(
                        model=model_id,
                        contents="Ping",
                        config=types.GenerateContentConfig(
                            max_output_tokens=5,
                            temperature=0.0,
                            thinking_config=types.ThinkingConfig(thinking_budget=0)
                        )
                    )
                    latency_ms = int((time.time() - t0) * 1000)
                    return True, f"Successfully connected to Gemini API via model '{model_id}'", {
                        "active_model": model_id,
                        "latency_ms": latency_ms,
                        "sdk": "google-genai",
                        "status": "healthy"
                    }
            except Exception as err:
                last_error = str(err)
                logger.warning("Test connection failed for model %s: %s", model_id, err)
                # If error is invalid API key (400/401/403), stop immediately
                err_str = str(err).lower()
                if "api_key" in err_str or "unauthenticated" in err_str or "permission" in err_str:
                    return False, f"Invalid API Key or unauthorized: {last_error[:120]}", {"status": "auth_error"}
                continue

        return False, f"LLM connectivity check failed: {last_error[:150]}", {"status": "unavailable"}

    def build_prompt(self, query: str, evidences: List[RetrievedEvidence]) -> str:
        evidence_blocks = []
        for ev in evidences:
            block = f"""--- EVIDENCE [{ev.ref_id}] ---
Source Title: {ev.title}
Section: {ev.section}
Relevance Score: {ev.similarity_score:.4f}
Source URL: {ev.url}
Content:
{ev.full_text}
"""
            evidence_blocks.append(block)

        context_str = "\n".join(evidence_blocks) if evidence_blocks else "No relevant passages were retrieved."

        prompt = f"""RETRIEVED KNOWLEDGE BASE PASSAGES:
=========================================
{context_str}
=========================================

USER INQUIRY:
{query}

Please provide a thoroughly grounded, cited research answer following the required structure."""
        return prompt

    @staticmethod
    def _extract_text(response: Any) -> Optional[str]:
        """Safely extracts text content across different Gemini SDK response structures."""
        if not response:
            return None
        # Direct .text attribute
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
        # Candidate parts
        if hasattr(response, 'candidates') and response.candidates:
            first_candidate = response.candidates[0]
            if hasattr(first_candidate, 'content') and first_candidate.content:
                parts = getattr(first_candidate.content, 'parts', [])
                extracted = []
                for p in parts:
                    txt = getattr(p, 'text', None)
                    if txt:
                        extracted.append(txt)
                if extracted:
                    return "".join(extracted).strip()
        return None

    def _call_model_with_retry(self, model_id: str, prompt: str, max_retries: int = 2) -> Optional[str]:
        """
        Calls a model with bounded exponential backoff for transient errors.
        Does not retry 404 (model not found) or auth errors.
        """
        from google.genai import types
        
        for attempt in range(max_retries + 1):
            try:
                # Fast RAG generation with thinking_budget=0
                config = types.GenerateContentConfig(
                    system_instruction=RAG_SYSTEM_INSTRUCTION,
                    temperature=settings.temperature,
                    max_output_tokens=settings.max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )
                response = self._client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=config
                )
                text = self._extract_text(response)
                if text:
                    return text
            except Exception as err:
                err_str = str(err).lower()
                # Permanent errors: fail immediately without retrying this model
                if "404" in err_str or "not_found" in err_str:
                    logger.warning("Model %s not found (404), skipping fallback.", model_id)
                    raise
                if "api_key" in err_str or "unauthenticated" in err_str or "permission" in err_str:
                    logger.error("Authentication error on model %s: %s", model_id, err)
                    raise

                # Transient errors: 503 unavailable, 429 rate limit
                if attempt < max_retries and ("503" in err_str or "429" in err_str or "deadline" in err_str or "timeout" in err_str):
                    backoff = (1.5 ** attempt) + random.uniform(0.1, 0.5)
                    logger.warning("Transient error on model %s (%s). Retrying in %.2fs (attempt %d/%d)...",
                                   model_id, err, backoff, attempt + 1, max_retries)
                    time.sleep(backoff)
                    continue
                logger.warning("Model %s failed on attempt %d: %s", model_id, attempt, err)
                raise
        return None

    def generate(self, query: str, evidences: List[RetrievedEvidence]) -> str:
        """
        Executes answer generation with multi-model fallback and safe error recovery.
        Never raises an unhandled exception that crashes the caller.
        """
        if not self.is_configured():
            if not self.api_key:
                return (
                    "⚠️ **Google Gemini API Key is required to synthesize AI research answers.**\n\n"
                    "Please configure your API key in the **Settings** panel or add `GEMINI_API_KEY` to your `.env` file.\n\n"
                    f"*{len(evidences)} relevant knowledge passages were successfully retrieved and can be inspected in the Evidence Panel on the right.*"
                )
            self._init_client()
            if not self.is_configured():
                return "❌ **Error: Could not connect to Google Gemini API.** Please verify your API key in Settings."

        prompt = self.build_prompt(query, evidences)

        # Primary: Modern Google GenAI SDK
        if getattr(self, '_is_modern_sdk', False) and self._client:
            # Build candidate model list with user preference first, followed by known available models
            candidates = [self.model_name] + [m for m in MODERN_CANDIDATE_MODELS if m != self.model_name]
            
            last_err = None
            for model_id in candidates:
                try:
                    logger.info("Attempting generation with model '%s'...", model_id)
                    text = self._call_model_with_retry(model_id, prompt, max_retries=1)
                    if text:
                        return text
                except Exception as err:
                    last_err = err
                    logger.warning("Candidate model '%s' failed: %s", model_id, err)
                    continue

            # If all modern models failed, format an actionable, non-crashing diagnostic message
            err_msg = str(last_err) if last_err else "All candidate models unavailable."
            return (
                f"⚠️ **AI Answer Generation Unavailable**\n\n"
                f"**Root Cause:** The Gemini API returned an error ({err_msg[:120]}).\n\n"
                f"**Diagnostics:** Checked models: `{', '.join(candidates)}`.\n\n"
                f"**Preserved Evidence:** {len(evidences)} relevant passage(s) were successfully retrieved from your knowledge base and are displayed in the Evidence Panel on the right."
            )

        # Fallback: Legacy SDK if available
        if hasattr(self, '_legacy_genai'):
            try:
                model = self._legacy_genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    system_instruction=RAG_SYSTEM_INSTRUCTION
                )
                resp = model.generate_content(
                    prompt,
                    generation_config=self._legacy_genai.GenerationConfig(
                        temperature=settings.temperature,
                        max_output_tokens=settings.max_output_tokens
                    )
                )
                if resp and resp.text:
                    return resp.text
            except Exception as e:
                logger.error("Legacy Gemini API generation failed: %s", e)
                return f"⚠️ Generation error via legacy Gemini API: {e}"

        return "⚠️ Generation failed. Please check your Gemini API key and model settings."

    def generate_stream(self, query: str, evidences: List[RetrievedEvidence]) -> Iterator[str]:
        """Yields response text chunks for live streaming."""
        if not self.is_configured():
            yield self.generate(query, evidences)
            return

        prompt = self.build_prompt(query, evidences)
        if getattr(self, '_is_modern_sdk', False) and self._client:
            from google.genai import types
            candidates = [self.model_name] + [m for m in MODERN_CANDIDATE_MODELS if m != self.model_name]

            for model_id in candidates:
                try:
                    config = types.GenerateContentConfig(
                        system_instruction=RAG_SYSTEM_INSTRUCTION,
                        temperature=settings.temperature,
                        max_output_tokens=settings.max_output_tokens,
                        thinking_config=types.ThinkingConfig(thinking_budget=0)
                    )
                    stream = self._client.models.generate_content_stream(
                        model=model_id,
                        contents=prompt,
                        config=config
                    )
                    for chunk in stream:
                        txt = self._extract_text(chunk)
                        if txt:
                            yield txt
                    return
                except Exception as e:
                    logger.warning("Streaming with model %s failed (%s), trying fallback...", model_id, e)
                    continue

        yield self.generate(query, evidences)
