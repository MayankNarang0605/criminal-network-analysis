"""
Graph Machine Learning & Link Prediction Module
Predicts unrecorded or missing relationships between suspects and entities
using topological proximity metrics (Adamic-Adar, Jaccard, Resource Allocation).
"""

from typing import Dict, List, Any, Optional, Tuple, Set
import math
import networkx as nx
from backend.app.graph.engine import CriminalGraphEngine

class LinkPredictor:
    """
    Evaluates entity pairs in the graph that do not currently have a direct edge
    and scores their likelihood of having an undisclosed or hidden criminal relationship.
    """
    def __init__(self, engine: CriminalGraphEngine):
        self.engine = engine

    def _get_entity_subgraph(self, target_labels: Optional[List[str]] = None) -> nx.Graph:
        """Constructs an undirected Graph filtered to specified node types (default: Person, Organization)."""
        labels = target_labels or ["Person", "Organization"]
        G = nx.Graph()

        for nid, data in self.engine.nodes_data.items():
            if data.get("label") in labels:
                G.add_node(nid, **data)

        # Include direct edges between these nodes OR 2-hop edges through intermediate assets/cases
        for edge in self.engine.edges_data.values():
            src = edge["source"]
            dst = edge["target"]
            if src in G and dst in G:
                G.add_edge(src, dst, weight=edge.get("weight", 1.0), relation_type=edge.get("relation_type"))

        # Also add implicit asset-sharing / co-occurrence edges to connect suspects through common assets
        for nid, data in self.engine.nodes_data.items():
            if data.get("label") not in labels:
                # Intermediate node (e.g. Phone, Vehicle, Case, Location)
                linked_entities = [
                    nb["node"]["id"] for nb in self.engine.get_neighbors(nid, direction="both")
                    if nb["node"].get("label") in labels
                ]
                for i in range(len(linked_entities)):
                    for j in range(i + 1, len(linked_entities)):
                        u, v = linked_entities[i], linked_entities[j]
                        if G.has_node(u) and G.has_node(v):
                            if G.has_edge(u, v):
                                G[u][v]["weight"] += 1.5
                            else:
                                G.add_edge(u, v, weight=1.5, relation_type=f"SHARED_{data.get('label').upper()}")

        return G

    def predict_missing_links(
        self,
        node_id: Optional[str] = None,
        top_k: int = 15,
        min_score: float = 0.2
    ) -> List[Dict[str, Any]]:
        """
        Generate link prediction suggestions. If node_id is provided, predicts for that entity;
        otherwise searches the global network for high-confidence unlinked suspect pairs.
        """
        if len(self.engine.nodes_data) < 3:
            return []

        G = self._get_entity_subgraph(["Person", "Organization"])
        if len(G.nodes()) < 2:
            return []

        # Find existing direct edges in the raw original graph to avoid suggesting already connected entities
        raw_connected_pairs: Set[Tuple[str, str]] = set()
        for e in self.engine.edges_data.values():
            raw_connected_pairs.add((e["source"], e["target"]))
            raw_connected_pairs.add((e["target"], e["source"]))

        candidate_pairs = []
        if node_id:
            node_id = str(node_id)
            if node_id not in G:
                return []
            for target_nid in G.nodes():
                if target_nid != node_id and (node_id, target_nid) not in raw_connected_pairs:
                    candidate_pairs.append((node_id, target_nid))
        else:
            nodes_list = list(G.nodes())
            for i in range(len(nodes_list)):
                for j in range(i + 1, len(nodes_list)):
                    u, v = nodes_list[i], nodes_list[j]
                    if (u, v) not in raw_connected_pairs:
                        candidate_pairs.append((u, v))

        if not candidate_pairs:
            return []

        predictions = []

        # Compute topological link metrics
        for u, v in candidate_pairs:
            u_neighbors = set(G.neighbors(u))
            v_neighbors = set(G.neighbors(v))
            common_neighbors = list(u_neighbors.intersection(v_neighbors))
            
            if not common_neighbors:
                continue

            # 1. Jaccard Coefficient
            union_len = len(u_neighbors.union(v_neighbors))
            jaccard = len(common_neighbors) / union_len if union_len > 0 else 0.0

            # 2. Adamic-Adar Index (penalizes high-degree common nodes, rewards rare shared ties)
            adamic_adar = 0.0
            for w in common_neighbors:
                degree_w = G.degree(w)
                if degree_w > 1:
                    adamic_adar += 1.0 / math.log(degree_w)

            # 3. Resource Allocation Index
            resource_alloc = 0.0
            for w in common_neighbors:
                degree_w = G.degree(w)
                if degree_w > 0:
                    resource_alloc += 1.0 / degree_w

            # Normalized Composite Score (0.0 to 1.0)
            composite_score = min(round((jaccard * 0.4) + (min(adamic_adar, 5.0) / 5.0 * 0.4) + (min(resource_alloc, 3.0) / 3.0 * 0.2), 3), 1.0)

            if composite_score >= min_score:
                u_node = self.engine.nodes_data.get(u, {})
                v_node = self.engine.nodes_data.get(v, {})
                
                common_node_names = [
                    f"{self.engine.nodes_data.get(w, {}).get('name')} ({self.engine.nodes_data.get(w, {}).get('label')})"
                    for w in common_neighbors[:4]
                ]

                # Evidence & Explainability
                explanation = (
                    f"Strong topological proximity (Confidence: {int(composite_score * 100)}%). "
                    f"Share {len(common_neighbors)} common intermediary associate(s) including: {', '.join(common_node_names)}. "
                    f"Adamic-Adar Index: {round(adamic_adar, 2)}, Jaccard: {round(jaccard, 2)}."
                )

                predictions.append({
                    "source_id": u,
                    "source_name": u_node.get("name"),
                    "source_label": u_node.get("label"),
                    "target_id": v,
                    "target_name": v_node.get("name"),
                    "target_label": v_node.get("label"),
                    "confidence_score": composite_score,
                    "predicted_relation": "PROBABLE_CO_CONSPIRATOR" if u_node.get("label") == "Person" and v_node.get("label") == "Person" else "UNDISCLOSED_LINK",
                    "common_associates_count": len(common_neighbors),
                    "common_associates": common_node_names,
                    "metrics": {
                        "jaccard_coefficient": round(jaccard, 4),
                        "adamic_adar_index": round(adamic_adar, 4),
                        "resource_allocation": round(resource_alloc, 4)
                    },
                    "evidence_explanation": explanation
                })

        # Sort descending by confidence score
        predictions.sort(key=lambda x: x["confidence_score"], reverse=True)
        return predictions[:top_k]
