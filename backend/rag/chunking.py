import re
import hashlib
from typing import List, Dict, Any, Optional
from llama_index.core.schema import TextNode, Document
from backend.config import settings

class AdvancedChunker:
    """
    Intelligent section-aware chunker that respects semantic boundaries
    (sections, paragraphs, sentences), attaches stable content hashes,
    and enriches each chunk with full traceability metadata.
    """
    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Approximate token count (rule-of-thumb: 1 token ≈ 4 characters or ~0.75 words)."""
        words = len(text.split())
        chars = len(text)
        return max(1, int((words * 1.33 + chars / 4) / 2))

    def split_into_sections(self, text: str) -> List[Dict[str, str]]:
        """Split text by Wikipedia header markers like '== Section ==', '=== Subsection ==='."""
        lines = text.split("\n")
        sections = []
        current_section = "Introduction"
        current_lines = []
        
        section_pattern = re.compile(r"^(={2,5})\s*(.*?)\s*\1$")
        
        for line in lines:
            match = section_pattern.match(line.strip())
            if match:
                # Flush previous section
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        sections.append({"section": current_section, "text": content})
                    current_lines = []
                current_section = match.group(2).strip()
            else:
                current_lines.append(line)
                
        if current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append({"section": current_section, "text": content})
                
        return sections if sections else [{"section": "Main", "text": text}]

    def chunk_text(self, text: str, max_chars: int, overlap_chars: int) -> List[str]:
        """
        Split section text into chunks respecting paragraph and sentence boundaries
        with token-budget overlap.
        """
        if len(text) <= max_chars:
            return [text] if text.strip() else []
        
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_len = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If paragraph itself exceeds max_chars, split by sentences
            if len(para) > max_chars:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    if current_len + len(sentence) + 1 > max_chars and current_chunk:
                        chunk_str = " ".join(current_chunk)
                        chunks.append(chunk_str)
                        # Carry over overlap
                        overlap_budget = overlap_chars
                        overlap_parts = []
                        for p in reversed(current_chunk):
                            if overlap_budget > 0:
                                overlap_parts.insert(0, p)
                                overlap_budget -= len(p)
                            else:
                                break
                        current_chunk = overlap_parts
                        current_len = sum(len(p) for p in current_chunk) + len(current_chunk)
                    current_chunk.append(sentence)
                    current_len += len(sentence) + 1
            else:
                if current_len + len(para) + 2 > max_chars and current_chunk:
                    chunk_str = "\n\n".join(current_chunk)
                    chunks.append(chunk_str)
                    overlap_budget = overlap_chars
                    overlap_parts = []
                    for p in reversed(current_chunk):
                        if overlap_budget > 0:
                            overlap_parts.insert(0, p)
                            overlap_budget -= len(p)
                        else:
                            break
                    current_chunk = overlap_parts
                    current_len = sum(len(p) for p in current_chunk) + len(current_chunk)
                current_chunk.append(para)
                current_len += len(para) + 2
                
        if current_chunk:
            chunk_str = "\n\n".join(current_chunk).strip()
            if chunk_str:
                chunks.append(chunk_str)
                
        return chunks

    def process_document(self, doc: Document) -> List[TextNode]:
        """Convert a Document into enriched TextNodes with deterministic metadata & chunk IDs."""
        if not doc.text or not doc.text.strip():
            return []

        title = doc.metadata.get("title", "Untitled Document")
        source_url = doc.metadata.get("url", "")
        doc_type = doc.metadata.get("type", "wikipedia")
        doc_rev = doc.metadata.get("revision_id", "")
        
        title_slug = re.sub(r'[^a-zA-Z0-9_]', '_', title)[:30].strip('_').lower()
        doc_hash = hashlib.md5(title.encode("utf-8")).hexdigest()[:6]
        article_id = f"{title_slug}_{doc_hash}"
        
        sections = self.split_into_sections(doc.text)
        nodes: List[TextNode] = []
        global_chunk_idx = 0

        # Maximum characters per chunk based on token budget (approx 4 chars per token)
        max_chars = self.chunk_size * 4
        overlap_chars = self.chunk_overlap * 4
        
        for sec in sections:
            section_name = sec["section"]
            sec_text = sec["text"]
            
            # Skip empty sections or boilerplate Wikipedia navigation
            if section_name.lower() in ["references", "see also", "further reading", "external links", "notes", "bibliography"]:
                continue
                
            raw_chunks = self.chunk_text(
                sec_text,
                max_chars=max_chars,
                overlap_chars=overlap_chars
            )
            
            for chunk_content in raw_chunks:
                clean_chunk = chunk_content.strip()
                if len(clean_chunk) < 30:
                    continue
                    
                chunk_id = f"{article_id}_c{global_chunk_idx:03d}"
                content_hash = hashlib.sha256(clean_chunk.encode("utf-8")).hexdigest()[:32]
                tokens_count = self.estimate_tokens(clean_chunk)

                node_metadata = {
                    "article_id": article_id,
                    "doc_title": title,
                    "title": title,
                    "source_url": source_url,
                    "source_type": doc_type,
                    "section": section_name,
                    "chunk_id": chunk_id,
                    "chunk_index": global_chunk_idx,
                    "content_hash": content_hash,
                    "char_count": len(clean_chunk),
                    "token_count": tokens_count,
                    "revision_id": doc_rev,
                    "ingestion_version": "2.0",
                }
                
                # Context prefix so embedding model understands section context
                enriched_text = f"[{title} — {section_name}]\n{clean_chunk}"
                
                node = TextNode(
                    id_=chunk_id,
                    text=clean_chunk,
                    metadata=node_metadata
                )
                nodes.append(node)
                global_chunk_idx += 1
                
        return nodes
