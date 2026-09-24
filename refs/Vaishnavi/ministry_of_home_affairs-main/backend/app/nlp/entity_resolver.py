"""
Entity Resolution & Normalization Module
Deduplicates entities across records, resolves aliases, matches phone/ID hashes,
and generates merge suggestions for human-in-the-loop review.
"""

from typing import Dict, List, Any, Optional, Tuple, Set
import difflib
from backend.app.graph.engine import CriminalGraphEngine

class EntityResolver:
    """
    Performs entity matching and resolution across criminal graph records.
    """
    def __init__(self, engine: CriminalGraphEngine):
        self.engine = engine

    @staticmethod
    def calculate_similarity(name1: str, name2: str) -> float:
        """Computes SequenceMatcher similarity score between two entity names."""
        n1 = name1.strip().lower()
        n2 = name2.strip().lower()
        if n1 == n2:
            return 1.0
        
        # Check sub-string inclusion (e.g. "Mohammed Aslam" vs "Aslam")
        if (len(n1) > 4 and n1 in n2) or (len(n2) > 4 and n2 in n1):
            return 0.85

        return round(difflib.SequenceMatcher(None, n1, n2).ratio(), 3)

    def find_merge_candidates(self, min_similarity: float = 0.75) -> List[Dict[str, Any]]:
        """
        Scans all Person entities in the graph to find probable duplicate entries
        that may refer to the same real-world individual.
        """
        persons = self.engine.get_all_nodes(label_filter="Person")
        candidates = []
        seen_pairs: Set[Tuple[str, str]] = set()

        for i in range(len(persons)):
            p1 = persons[i]
            for j in range(i + 1, len(persons)):
                p2 = persons[j]
                pair_key = tuple(sorted([p1["id"], p2["id"]]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                match_reasons = []
                score = 0.0

                # 1. Phone Hash match
                p1_phone = p1.get("phone_hash") or p1.get("phone")
                p2_phone = p2.get("phone_hash") or p2.get("phone")
                if p1_phone and p2_phone and p1_phone == p2_phone:
                    score += 0.95
                    match_reasons.append(f"Exact Phone Number Match ({p1_phone})")

                # 2. National ID / PAN Hash match
                p1_id = p1.get("national_id_hash")
                p2_id = p2.get("national_id_hash")
                if p1_id and p2_id and p1_id == p2_id:
                    score += 0.98
                    match_reasons.append("Exact National ID / PAN Match")

                # 3. Name Similarity
                name_sim = self.calculate_similarity(p1.get("name", ""), p2.get("name", ""))
                if name_sim >= min_similarity:
                    score = max(score, name_sim)
                    match_reasons.append(f"High Name Similarity ({int(name_sim * 100)}%)")

                # 4. Shared Alias match
                p1_aliases = set(a.lower() for a in p1.get("aliases", []))
                p2_aliases = set(a.lower() for a in p2.get("aliases", []))
                common_aliases = p1_aliases.intersection(p2_aliases)
                if common_aliases:
                    score = max(score, 0.88)
                    match_reasons.append(f"Shared Alias: {', '.join(common_aliases)}")

                # 5. Shared Vehicle or Financial Account
                p1_neighbors = {nb["node"]["id"] for nb in self.engine.get_neighbors(p1["id"])}
                p2_neighbors = {nb["node"]["id"] for nb in self.engine.get_neighbors(p2["id"])}
                shared_assets = p1_neighbors.intersection(p2_neighbors)
                if shared_assets:
                    score = min(score + 0.15, 1.0)
                    match_reasons.append(f"Shares {len(shared_assets)} connected asset/case nodes")

                if score >= min_similarity:
                    candidates.append({
                        "entity_type": "Person",
                        "primary_id": p1["id"],
                        "primary_name": p1.get("name"),
                        "candidate_id": p2["id"],
                        "candidate_name": p2.get("name"),
                        "similarity_score": round(score, 2),
                        "match_reasons": match_reasons,
                        "status": "PENDING"
                    })

        candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
        return candidates

    def execute_merge(self, primary_id: str, candidate_id: str) -> Dict[str, Any]:
        """
        Merges candidate_id into primary_id in the graph:
        Transfers all edges from candidate to primary, combines aliases & attributes,
        and removes candidate node.
        """
        primary_id = str(primary_id)
        candidate_id = str(candidate_id)

        if primary_id not in self.engine.graph or candidate_id not in self.engine.graph:
            raise ValueError("Both entities must exist in the graph to perform merge.")

        primary_node = self.engine.nodes_data[primary_id]
        candidate_node = self.engine.nodes_data[candidate_id]

        # Combine aliases
        p_aliases = set(primary_node.get("aliases", []))
        c_aliases = set(candidate_node.get("aliases", []))
        p_aliases.add(candidate_node.get("name"))
        p_aliases.update(c_aliases)
        primary_node["aliases"] = list(p_aliases)

        # Transfer Outbound edges
        for _, target, edge_data in list(self.engine.graph.out_edges(candidate_id, data=True)):
            if target != primary_id:
                try:
                    self.engine.add_edge(
                        primary_id, target,
                        edge_data.get("relation_type", "MERGED_REL"),
                        edge_data
                    )
                except Exception:
                    pass

        # Transfer Inbound edges
        for source, _, edge_data in list(self.engine.graph.in_edges(candidate_id, data=True)):
            if source != primary_id:
                try:
                    self.engine.add_edge(
                        source, primary_id,
                        edge_data.get("relation_type", "MERGED_REL"),
                        edge_data
                    )
                except Exception:
                    pass

        # Remove candidate node from graph & indices
        self.engine.graph.remove_node(candidate_id)
        self.engine.nodes_data.pop(candidate_id, None)

        # Persist graph changes
        self.engine.save_to_disk()

        return {
            "success": True,
            "message": f"Successfully merged '{candidate_node.get('name')}' ({candidate_id}) into '{primary_node.get('name')}' ({primary_id}).",
            "primary_node": primary_node
        }
