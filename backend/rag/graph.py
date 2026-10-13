import math
import hashlib
from typing import List, Dict, Any, Optional
from llama_index.core.schema import TextNode

class KnowledgeGraphBuilder:
    """
    Constructs a 3D vector-space graph representation of documents,
    chunks, semantic clusters, and query retrieval rays for Three.js.
    """
    @classmethod
    def build_graph(
        cls,
        documents_meta: List[Dict[str, Any]],
        chunk_nodes: List[TextNode],
        active_query: Optional[str] = None,
        retrieved_chunk_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        retrieved_ids = set(retrieved_chunk_ids or [])
        nodes = []
        links = []

        doc_positions = {}
        total_docs = max(1, len(documents_meta))
        
        # 1. Document Cluster Center Nodes
        for i, doc in enumerate(documents_meta):
            title = doc["title"]
            # Arrange multiple document centers in a wide orbit ring
            angle = (2 * math.pi * i) / total_docs
            dist = 14.0 if total_docs > 1 else 0.0
            doc_x = round(dist * math.cos(angle), 2)
            doc_y = round(math.sin(i * 1.5) * 2.5, 2)
            doc_z = round(dist * math.sin(angle), 2)
            
            doc_id = f"doc_{hashlib.md5(title.encode()).hexdigest()[:8]}"
            doc_positions[title] = (doc_x, doc_y, doc_z)

            nodes.append({
                "id": doc_id,
                "name": title,
                "type": "document",
                "val": 14,
                "color": "#38BDF8",  # Radiant Luminous Cyan
                "url": doc.get("url", ""),
                "char_count": doc.get("char_count", 0),
                "chunks_count": doc.get("chunks_count", 0),
                "x": doc_x,
                "y": doc_y,
                "z": doc_z,
            })

        # 2. Chunk Nodes clustered around their parent document with Fibonacci spherical galaxy spread
        doc_chunk_counters: Dict[str, int] = {}
        golden_angle = 2.399963229728653  # pi * (3 - sqrt(5))

        for node in chunk_nodes:
            meta = node.metadata or {}
            title = meta.get("doc_title") or meta.get("title") or "Unknown"
            doc_x, doc_y, doc_z = doc_positions.get(title, (0, 0, 0))
            
            counter = doc_chunk_counters.get(title, 0)
            doc_chunk_counters[title] = counter + 1
            
            # Fibonacci spherical galaxy distribution to prevent any overlapping
            theta = counter * golden_angle
            
            # Distance scales gracefully with square root of chunk index
            # Layered expansion from 3.5 to 13.5 units
            r = 3.2 + math.sqrt(counter + 1) * 0.78
            
            # Inclination angle mapping across sphere
            norm_idx = (counter * 0.618033988749895) % 1.0
            phi = math.acos(max(-0.95, min(0.95, 1.0 - 2.0 * norm_idx)))
            
            cx = round(doc_x + r * math.sin(phi) * math.cos(theta), 2)
            cy = round(doc_y + (r * 0.55) * math.cos(phi), 2)  # subtle galaxy disc flattening
            cz = round(doc_z + r * math.sin(phi) * math.sin(theta), 2)

            is_retrieved = node.node_id in retrieved_ids
            # Radiant Emerald if retrieved evidence, Electric Indigo/Periwinkle if standard
            color = "#34D399" if is_retrieved else "#818CF8"

            chunk_node = {
                "id": node.node_id,
                "name": f"{title} [{meta.get('section', 'Chunk')}]",
                "type": "chunk",
                "val": 6 if is_retrieved else 2.5,
                "color": color,
                "is_retrieved": is_retrieved,
                "section": meta.get("section", ""),
                "doc_title": title,
                "preview": node.get_content()[:120] + "...",
                "x": cx,
                "y": cy,
                "z": cz,
            }
            nodes.append(chunk_node)

            # Link to document parent
            doc_id = f"doc_{hashlib.md5(title.encode()).hexdigest()[:8]}"
            links.append({
                "source": doc_id,
                "target": node.node_id,
                "type": "membership",
                "color": "rgba(99, 102, 241, 0.22)"
            })

        # 3. Query Node (if active query present)
        if active_query:
            query_id = "node_active_query"
            nodes.append({
                "id": query_id,
                "name": f"Query: {active_query[:35]}...",
                "type": "query",
                "val": 16,
                "color": "#F59E0B",  # Radiant Amber Gold
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
            })

            # Retrieval rays from query to retrieved chunks
            for cid in retrieved_ids:
                links.append({
                    "source": query_id,
                    "target": cid,
                    "type": "retrieval_ray",
                    "color": "#34D399",  # Glowing Emerald Laser Ray
                    "animated": True
                })

        return {
            "nodes": nodes,
            "links": links,
            "stats": {
                "total_nodes": len(nodes),
                "total_links": len(links),
                "documents": len(documents_meta),
                "chunks": len(chunk_nodes),
                "retrieved": len(retrieved_ids)
            }
        }
