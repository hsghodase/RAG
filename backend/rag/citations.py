import re
from typing import List, Dict, Any, Set
from backend.rag.retrieval import RetrievedEvidence

class CitationManager:
    """
    Parses, validates, and manages source citations in RAG answers.
    Converts raw REF references into rich interactive citation objects.
    """
    CITATION_REGEX = re.compile(r'\[(REF-\d+|REF_\d+)\]', re.IGNORECASE)

    @classmethod
    def extract_cited_refs(cls, text: str) -> Set[str]:
        """Finds all unique citation keys in the text, e.g. {'REF-1', 'REF-2'}."""
        matches = cls.CITATION_REGEX.findall(text)
        cleaned = set()
        for m in matches:
            standardized = m.upper().replace('_', '-')
            cleaned.add(standardized)
        return cleaned

    @classmethod
    def process_citations(
        cls,
        answer_text: str,
        evidences: List[RetrievedEvidence]
    ) -> Dict[str, Any]:
        """
        Correlates citations in answer with retrieved evidences,
        tagging which ones were explicitly cited vs un-cited supplementary evidence.
        """
        cited_keys = cls.extract_cited_refs(answer_text)
        evidence_map = {ev.ref_id: ev for ev in evidences}

        citation_cards = []
        for ev in evidences:
            is_cited = ev.ref_id in cited_keys
            card = ev.to_dict()
            card["is_directly_cited"] = is_cited
            citation_cards.append(card)

        # Sort: directly cited first, then by similarity score
        citation_cards.sort(key=lambda c: (not c["is_directly_cited"], -c["similarity_score"]))

        return {
            "total_retrieved": len(evidences),
            "total_cited": len(cited_keys),
            "cited_keys": list(cited_keys),
            "cards": citation_cards
        }
