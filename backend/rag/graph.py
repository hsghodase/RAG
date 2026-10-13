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
            # Arrange document centers in a wide ring in X-Z plane
            angle = (2 * math.pi * i) / total_docs
            dist = 8.0 if total_docs > 1 else 0.0
            doc_x = round(dist * math.cos(angle), 2)
            doc_y = round(math.sin(i * 1.5) * 2.0, 2)
            doc_z = round(dist * math.sin(angle), 2)
            
            doc_id = f"doc_{hashlib.md5(title.encode()).hexdigest()[:8]}"
            doc_positions[title] = (doc_x, doc_y, doc_z)

            nodes.append({
                "id": doc_id,
                "name": title,
                "type": "document",
                "val": 12,  # Node size
                "color": "#9DB2BF",  # Soft Frost Slate Blue
                "url": doc.get("url", ""),
                "char_count": doc.get("char_count", 0),
                "chunks_count": doc.get("chunks_count", 0),
                "x": doc_x,
                "y": doc_y,
                "z": doc_z,
            })

        # 2. Chunk Nodes clustered around their parent document
        doc_chunk_counters: Dict[str, int] = {}
        for node in chunk_nodes:
            meta = node.metadata or {}
            title = meta.get("doc_title") or meta.get("title") or "Unknown"
            doc_x, doc_y, doc_z = doc_positions.get(title, (0, 0, 0))
            
            counter = doc_chunk_counters.get(title, 0)
            doc_chunk_counters[title] = counter + 1
            
            # Spherical orbit offset around document center
            phi = (counter * 137.5) * (math.pi / 180.0) # golden angle
            rad = 2.5 + (counter % 3) * 0.8
            h_offset = ((counter % 5) - 2) * 0.7
            
            cx = round(doc_x + rad * math.cos(phi), 2)
            cy = round(doc_y + h_offset, 2)
            cz = round(doc_z + rad * math.sin(phi), 2)

            is_retrieved = node.node_id in retrieved_ids
            color = "#DDE6ED" if is_retrieved else "#526D82"  # Ice Platinum if retrieved evidence, Steel Slate if standard

            chunk_node = {
                "id": node.node_id,
                "name": f"{title} [{meta.get('section', 'Chunk')}]",
                "type": "chunk",
                "val": 6 if is_retrieved else 3,
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
                "color": "rgba(157, 178, 191, 0.25)"
            })

        # 3. Query Node (if active query present)
        if active_query:
            query_id = "node_active_query"
            nodes.append({
                "id": query_id,
                "name": f"Query: {active_query[:35]}...",
                "type": "query",
                "val": 15,
                "color": "#DDE6ED",  # Radiant Ice White
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
                    "color": "#DDE6ED",  # Glowing ice platinum ray
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
