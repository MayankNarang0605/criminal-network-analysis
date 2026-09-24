"""
Graph Database Engine
Multi-Relational In-Memory Property Graph with NetworkX and Persistent JSON/SQLite storage
"""

import json
import os
from typing import Dict, List, Any, Optional, Set, Tuple
import networkx as nx
from backend.app.config import GRAPH_DATA_PATH
from backend.app.graph.schema import Node, Edge

class CriminalGraphEngine:
    """
    High-Performance Graph Engine managing nodes, multi-relational edges,
    neighborhood traversals, and fast attribute lookups.
    """
    def __init__(self, persistence_path: Optional[str] = None):
        self.persistence_path = persistence_path or GRAPH_DATA_PATH
        # MultiDiGraph allows multiple directed relations between same nodes
        self.graph = nx.MultiDiGraph()
        # Fast lookup indices
        self.nodes_data: Dict[str, Dict[str, Any]] = {}
        self.edges_data: Dict[str, Dict[str, Any]] = {}
        self.phone_index: Dict[str, str] = {}         # phone_hash -> node_id
        self.account_index: Dict[str, str] = {}       # account_hash -> node_id
        self.vehicle_index: Dict[str, str] = {}       # registration_number -> node_id
        self.case_index: Dict[str, str] = {}          # case_id / fir_number -> node_id
        self.id_index: Dict[str, str] = {}            # national_id_hash -> node_id

        # Load existing graph if available
        if os.path.exists(self.persistence_path):
            self.load_from_disk()

    def add_node(
        self,
        node_id: str,
        label: str,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Insert or update a node in the graph and update lookup indices."""
        node_id = str(node_id)
        attrs = attributes or {}
        
        # Preserve or initialize risk score and timestamps
        if "risk_score" not in attrs and label == "Person":
            attrs["risk_score"] = 0.0

        node_obj = Node(node_id, label, name, attrs)
        node_dict = node_obj.to_dict()

        self.graph.add_node(node_id, **node_dict)
        self.nodes_data[node_id] = node_dict

        # Indexing for Entity Resolution
        if "phone_hash" in attrs:
            self.phone_index[attrs["phone_hash"]] = node_id
        if "account_hash" in attrs:
            self.account_index[attrs["account_hash"]] = node_id
        if "registration_number" in attrs:
            self.vehicle_index[str(attrs["registration_number"]).upper().replace(" ", "")] = node_id
        if "case_id" in attrs:
            self.case_index[attrs["case_id"]] = node_id
        if "fir_number" in attrs:
            self.case_index[attrs["fir_number"]] = node_id
        if "national_id_hash" in attrs:
            self.id_index[attrs["national_id_hash"]] = node_id

        return node_dict

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        attributes: Optional[Dict[str, Any]] = None,
        edge_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Insert a directed relationship edge between two nodes."""
        source_id = str(source_id)
        target_id = str(target_id)
        
        if source_id not in self.graph or target_id not in self.graph:
            raise ValueError(f"Both source '{source_id}' and target '{target_id}' must exist before creating edge.")

        if not edge_id:
            edge_id = f"edge_{source_id}_{relation_type}_{target_id}_{len(self.edges_data) + 1}"

        edge_obj = Edge(edge_id, source_id, target_id, relation_type, attributes)
        edge_dict = edge_obj.to_dict()

        self.graph.add_edge(source_id, target_id, key=edge_id, **edge_dict)
        self.edges_data[edge_id] = edge_dict

        return edge_dict

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve node data dictionary by ID."""
        return self.nodes_data.get(str(node_id))

    def get_all_nodes(self, label_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all nodes, optionally filtered by label."""
        if not label_filter:
            return list(self.nodes_data.values())
        return [n for n in self.nodes_data.values() if n.get("label") == label_filter]

    def get_all_edges(self, type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all edges, optionally filtered by relation type."""
        if not type_filter:
            return list(self.edges_data.values())
        return [e for e in self.edges_data.values() if e.get("relation_type") == type_filter]

    def get_neighbors(self, node_id: str, direction: str = "both") -> List[Dict[str, Any]]:
        """Retrieve 1-hop connected nodes with relation context."""
        node_id = str(node_id)
        if node_id not in self.graph:
            return []

        neighbor_nodes = []
        if direction in ("out", "both"):
            for _, target, edge_data in self.graph.out_edges(node_id, data=True):
                target_node = self.get_node(target)
                if target_node:
                    neighbor_nodes.append({
                        "node": target_node,
                        "relation": edge_data.get("relation_type"),
                        "direction": "outbound",
                        "edge": edge_data
                    })

        if direction in ("in", "both"):
            for source, _, edge_data in self.graph.in_edges(node_id, data=True):
                source_node = self.get_node(source)
                if source_node:
                    neighbor_nodes.append({
                        "node": source_node,
                        "relation": edge_data.get("relation_type"),
                        "direction": "inbound",
                        "edge": edge_data
                    })

        return neighbor_nodes

    def get_ego_graph(self, center_node_id: str, radius: int = 1) -> Dict[str, Any]:
        """
        Extract sub-graph containing the center node and its k-hop neighborhood.
        Ideal for 360° suspect network exploration.
        """
        center_node_id = str(center_node_id)
        if center_node_id not in self.graph:
            return {"nodes": [], "edges": [], "center_id": center_node_id}

        # Convert to undirected view for ego-network expansion
        undirected_g = self.graph.to_undirected(as_view=True)
        ego_nodes_set = set(nx.ego_graph(undirected_g, center_node_id, radius=radius).nodes())

        sub_nodes = [self.nodes_data[nid] for nid in ego_nodes_set if nid in self.nodes_data]
        sub_edges = [
            e for e in self.edges_data.values()
            if e["source"] in ego_nodes_set and e["target"] in ego_nodes_set
        ]

        return {
            "center_id": center_node_id,
            "radius": radius,
            "nodes": sub_nodes,
            "edges": sub_edges,
            "node_count": len(sub_nodes),
            "edge_count": len(sub_edges)
        }

    def search_nodes(self, query: str, label_filter: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
        """Search nodes by name, alias, phone, vehicle, account, or case number."""
        query = query.strip().lower()
        if not query:
            return []

        results = []
        for n in self.nodes_data.values():
            if label_filter and n.get("label") != label_filter:
                continue

            name = str(n.get("name", "")).lower()
            node_id = str(n.get("id", "")).lower()
            aliases = [str(a).lower() for a in n.get("aliases", [])]
            phone = str(n.get("phone", "")).lower()
            fir = str(n.get("fir_number", "")).lower()
            reg = str(n.get("registration_number", "")).lower()
            acc = str(n.get("account_number", "")).lower()
            station = str(n.get("station", "")).lower()

            matched = (
                query in name or
                query in node_id or
                any(query in a for a in aliases) or
                query in phone or
                query in fir or
                query in reg or
                query in acc or
                query in station
            )

            if matched:
                results.append(n)
                if len(results) >= limit:
                    break

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Returns structural statistics of the network."""
        label_counts = {}
        for n in self.nodes_data.values():
            lbl = n.get("label", "Unknown")
            label_counts[lbl] = label_counts.get(lbl, 0) + 1

        edge_counts = {}
        for e in self.edges_data.values():
            rel = e.get("relation_type", "Unknown")
            edge_counts[rel] = edge_counts.get(rel, 0) + 1

        return {
            "total_nodes": len(self.nodes_data),
            "total_edges": len(self.edges_data),
            "node_distribution": label_counts,
            "edge_distribution": edge_counts,
            "is_connected": nx.is_weakly_connected(self.graph) if len(self.nodes_data) > 0 else False
        }

    def save_to_disk(self, filepath: Optional[str] = None):
        """Persist graph store to JSON format on disk."""
        target_path = filepath or self.persistence_path
        data = {
            "nodes": list(self.nodes_data.values()),
            "edges": list(self.edges_data.values())
        }
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_from_disk(self, filepath: Optional[str] = None):
        """Load graph store from JSON format on disk."""
        target_path = filepath or self.persistence_path
        if not os.path.exists(target_path):
            return

        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.clear()
        for node in data.get("nodes", []):
            node_id = node.get("id")
            label = node.get("label")
            name = node.get("name")
            attrs = {k: v for k, v in node.items() if k not in ("id", "label", "name")}
            self.add_node(node_id, label, name, attrs)

        for edge in data.get("edges", []):
            edge_id = edge.get("id")
            source = edge.get("source")
            target = edge.get("target")
            rel = edge.get("relation_type")
            attrs = {k: v for k, v in edge.items() if k not in ("id", "source", "target", "relation_type")}
            self.add_edge(source, target, rel, attrs, edge_id=edge_id)

    def clear(self):
        """Reset the graph in-memory."""
        self.graph.clear()
        self.nodes_data.clear()
        self.edges_data.clear()
        self.phone_index.clear()
        self.account_index.clear()
        self.vehicle_index.clear()
        self.case_index.clear()
        self.id_index.clear()


# Global Singleton Instance of Criminal Graph Engine
graph_engine = CriminalGraphEngine()
