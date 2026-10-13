import math
import hashlib
from typing import List, Dict, Any, Optional
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore
from backend.config import settings

class RetrievedEvidence:
    def __init__(
        self,
        ref_id: str,
        chunk_id: str,
        title: str,
        section: str,
        url: str,
        source_type: str,
        similarity_score: float,
        full_text: str,
        preview: str,
        char_count: int,
        token_count: int = 0,
        article_id: str = "",
        score_explanation: str = "",
        vector_coords: Optional[Dict[str, float]] = None
    ):
        self.ref_id = ref_id
        self.chunk_id = chunk_id
        self.title = title
        self.section = section
        self.url = url
        self.source_type = source_type
        self.similarity_score = similarity_score
        self.full_text = full_text
        self.preview = preview
        self.char_count = char_count
        self.token_count = token_count or max(1, char_count // 4)
        self.article_id = article_id
        self.score_explanation = score_explanation or self._explain_score(similarity_score)
        self.vector_coords = vector_coords or {"x": 0.0, "y": 0.0, "z": 0.0}

    @staticmethod
    def _explain_score(score: float) -> str:
        pct = int(min(1.0, max(0.0, score)) * 100)
        if score >= 0.70:
            return f"High Match ({pct}%): Strong semantic congruence with query."
        elif score >= 0.40:
            return f"Moderate Match ({pct}%): Relevant background/context passage."
        else:
            return f"Weak Match ({pct}%): Peripheral semantic similarity."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref_id": self.ref_id,
            "chunk_id": self.chunk_id,
            "article_id": self.article_id,
            "title": self.title,
            "section": self.section,
            "url": self.url,
            "source_type": self.source_type,
            "similarity_score": round(self.similarity_score, 4),
            "score_explanation": self.score_explanation,
            "full_text": self.full_text,
            "preview": self.preview,
            "char_count": self.char_count,
            "token_count": self.token_count,
            "vector_coords": self.vector_coords
        }

class RAGRetriever:
    """
    Robust retrieval layer with similarity threshold filtering,
    article selection scope filtering, content deduplication,
    token-budget clipping, and 3D spatial vector projection.
    """
    def __init__(self, index: VectorStoreIndex):
        self.index = index

    @staticmethod
    def _project_to_3d(text: str, score: float, index: int, total: int) -> Dict[str, float]:
        """
        Calculates a deterministic 3D coordinate for vector space visualization.
        High relevance nodes are pulled closer to the central query (radius inverse to score).
        """
        h = hashlib.sha256(text[:100].encode()).hexdigest()
        theta = (int(h[:8], 16) % 360) * (math.pi / 180.0)
        phi = (int(h[8:16], 16) % 180) * (math.pi / 180.0)
        
        radius = max(1.5, 6.0 * (1.0 - min(1.0, max(0.0, score))))
        
        x = radius * math.sin(phi) * math.cos(theta)
        y = radius * math.cos(phi) * 0.7
        z = radius * math.sin(phi) * math.sin(theta)
        
        return {"x": round(x, 2), "y": round(y, 2), "z": round(z, 2)}

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        article_filter: Optional[List[str]] = None,
        max_token_budget: Optional[int] = None
    ) -> List[RetrievedEvidence]:
        k = top_k or settings.top_k
        thresh = similarity_threshold if similarity_threshold is not None else settings.similarity_threshold
        budget = max_token_budget or settings.context_token_budget

        filter_set = {a.strip().lower() for a in article_filter} if article_filter else None

        # Fetch extra nodes to allow post-filtering and deduplication
        retrieval_k = max(k * 3, 20)
        retriever = self.index.as_retriever(similarity_top_k=retrieval_k)
        raw_nodes: List[NodeWithScore] = retriever.retrieve(query)

        seen_snippets = set()
        evidences: List[RetrievedEvidence] = []
        ref_counter = 1
        current_token_count = 0

        for node_with_score in raw_nodes:
            score = float(getattr(node_with_score, "score", 0.0) or 0.0)
            node = node_with_score.node
            meta = node.metadata or {}
            
            title = meta.get("title") or meta.get("doc_title") or "Wikipedia"
            clean_title = title.strip().lower()
            article_id = meta.get("article_id") or ""

            # 1. Article Scope Filter
            if filter_set is not None:
                if clean_title not in filter_set and article_id.lower() not in filter_set:
                    continue

            # 2. Similarity threshold filter (allow at least 1 top result if above 0.1)
            if score < thresh and len(evidences) >= 1:
                continue

            text = node.get_content().strip()
            if not text:
                continue

            # 3. Content deduplication by 80-char normalized snippet
            norm_snippet = "".join(text.split())[:80].lower()
            if norm_snippet in seen_snippets:
                continue
            seen_snippets.add(norm_snippet)

            section = meta.get("section") or "Overview"
            url = meta.get("source_url") or meta.get("url") or f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            source_type = meta.get("source_type") or meta.get("type") or "wikipedia"
            chunk_id = meta.get("chunk_id") or node.node_id

            # Estimate tokens
            tokens_in_chunk = meta.get("token_count") or max(1, len(text) // 4)
            if current_token_count + tokens_in_chunk > budget and len(evidences) >= 2:
                # Token budget reached
                break
            current_token_count += tokens_in_chunk

            words = text.split()
            preview = " ".join(words[:25]) + ("..." if len(words) > 25 else "")
            coords = self._project_to_3d(text, score, ref_counter, k)

            evidence = RetrievedEvidence(
                ref_id=f"REF-{ref_counter}",
                chunk_id=chunk_id,
                article_id=article_id,
                title=title,
                section=section,
                url=url,
                source_type=source_type,
                similarity_score=score,
                full_text=text,
                preview=preview,
                char_count=len(text),
                token_count=tokens_in_chunk,
                vector_coords=coords
            )
            evidences.append(evidence)
            ref_counter += 1

            if len(evidences) >= k:
                break

        return evidences
