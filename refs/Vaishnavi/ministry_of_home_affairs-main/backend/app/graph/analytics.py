"""
Network Science & Graph Analytics Module
Centrality Metrics, Louvain Community Detection, Shortest Path,
Composite Law-Enforcement Risk Scoring, and Cross-Jurisdictional Case Linkage.
"""

from typing import Dict, List, Any, Optional, Tuple, Set
import networkx as nx
from backend.app.graph.engine import CriminalGraphEngine

class GraphAnalytics:
    """
    Computes network metrics and intelligence indicators from the criminal graph.
    """
    def __init__(self, engine: CriminalGraphEngine):
        self.engine = engine

    def _get_undirected_view(self) -> nx.Graph:
        """Helper to create a simple undirected weighted Graph view for community and path analysis."""
        G = nx.Graph()
        for node_id, data in self.engine.nodes_data.items():
            G.add_node(node_id, **data)

        for edge in self.engine.edges_data.values():
            src = edge["source"]
            dst = edge["target"]
            weight = edge.get("weight", 1.0)
            if G.has_edge(src, dst):
                G[src][dst]["weight"] += weight
            else:
                G.add_edge(src, dst, weight=weight, relation_type=edge.get("relation_type"))

        return G

    def compute_centrality_metrics(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate Degree, Betweenness, Closeness, and PageRank centralities for all nodes.
        """
        if len(self.engine.graph) == 0:
            return {}

        G_undirected = self._get_undirected_view()
        
        # Centralities
        deg_centrality = nx.degree_centrality(G_undirected)
        betweenness = nx.betweenness_centrality(G_undirected, weight="weight")
        
        # Closeness
        closeness = nx.closeness_centrality(G_undirected)
        
        # PageRank (influence score)
        try:
            pagerank = nx.pagerank(G_undirected, weight="weight", max_iter=200)
        except Exception:
            pagerank = {n: 1.0 / len(G_undirected) for n in G_undirected.nodes()}

        results = {}
        for node_id in G_undirected.nodes():
            results[node_id] = {
                "degree_centrality": round(deg_centrality.get(node_id, 0.0), 4),
                "betweenness_centrality": round(betweenness.get(node_id, 0.0), 4),
                "closeness_centrality": round(closeness.get(node_id, 0.0), 4),
                "pagerank": round(pagerank.get(node_id, 0.0), 4)
            }

        return results

    def compute_composite_risk_score(self) -> List[Dict[str, Any]]:
        """
        Calculates a 0-100 composite risk score for all Person nodes.
        Combines:
        1. Network Centrality (PageRank + Betweenness broker role)
        2. Connected FIR / Case Severity (e.g. Cyber Fraud, Terror Financing, Extortion)
        3. Cross-Jurisdiction Span (active in multiple police stations)
        4. Degree of Direct Criminal Associates
        Includes Explainable AI (XAI) breakdown.
        """
        centralities = self.compute_centrality_metrics()
        person_nodes = self.engine.get_all_nodes(label_filter="Person")

        ranked_persons = []
        for person in person_nodes:
            node_id = person["id"]
            node_cent = centralities.get(node_id, {
                "degree_centrality": 0.0,
                "betweenness_centrality": 0.0,
                "closeness_centrality": 0.0,
                "pagerank": 0.0
            })

            # Inspect connections for case severity & cross-jurisdictions
            neighbors = self.engine.get_neighbors(node_id, direction="both")
            cases_linked = []
            jurisdictions = set()
            associate_count = 0
            financial_count = 0
            vehicle_count = 0

            for nb in neighbors:
                nb_node = nb["node"]
                lbl = nb_node.get("label")
                if lbl == "Case":
                    cases_linked.append(nb_node)
                    if "jurisdiction_code" in nb_node:
                        jurisdictions.add(nb_node["jurisdiction_code"])
                elif lbl == "Person":
                    associate_count += 1
                elif lbl == "FinancialAccount":
                    financial_count += 1
                elif lbl == "Vehicle":
                    vehicle_count += 1

            # Factor 1: Network Centrality Score (Max 35 pts)
            # PageRank captures hierarchical kingpin influence; betweenness captures broker/middleman
            pr_score = min(node_cent["pagerank"] * 500, 20.0)
            bw_score = min(node_cent["betweenness_centrality"] * 50, 15.0)
            network_score = pr_score + bw_score

            # Factor 2: Case Involvement & Severity (Max 35 pts)
            case_score = 0.0
            severity_reasons = []
            for case in cases_linked:
                cat = case.get("crime_category", "")
                if "Terror" in cat or "Organized" in cat:
                    case_score += 15.0
                    severity_reasons.append(f"High-Severity Crime: {cat}")
                elif "Cyber Fraud" in cat or "Narcotics" in cat or "FICN" in cat:
                    case_score += 10.0
                    severity_reasons.append(f"Major Financial/Narcotics Crime: {cat}")
                else:
                    case_score += 7.0
                    severity_reasons.append(f"Case: {cat}")
            case_score = min(case_score, 35.0)

            # Factor 3: Multi-Jurisdictional Cross-Linking (Max 15 pts)
            jurisdiction_score = min(len(jurisdictions) * 7.5, 15.0)

            # Factor 4: Asset & Communication Velocity (Max 15 pts)
            asset_score = min((associate_count * 2.5) + (financial_count * 3.0) + (vehicle_count * 2.5), 15.0)

            # Total Composite Risk (0 - 100)
            total_risk = min(round(network_score + case_score + jurisdiction_score + asset_score, 1), 100.0)

            # Assign Role Classification
            if total_risk >= 75.0 or node_cent["pagerank"] > 0.05:
                operational_role = "Kingpin / Syndicate Mastermind"
                risk_tier = "CRITICAL"
            elif node_cent["betweenness_centrality"] > 0.08:
                operational_role = "Intermediary / Cross-Cell Broker"
                risk_tier = "HIGH"
            elif len(cases_linked) > 1 or total_risk >= 50.0:
                operational_role = "Core Operative / Key Accused"
                risk_tier = "HIGH"
            elif total_risk >= 30.0:
                operational_role = "Cell Member / Mule / Associate"
                risk_tier = "MEDIUM"
            else:
                operational_role = "Peripheral Contact"
                risk_tier = "LOW"

            # Update in node attributes
            person["risk_score"] = total_risk
            person["operational_role"] = operational_role
            person["risk_tier"] = risk_tier

            ranked_persons.append({
                "id": node_id,
                "name": person.get("name"),
                "aliases": person.get("aliases", []),
                "operational_role": operational_role,
                "risk_tier": risk_tier,
                "risk_score": total_risk,
                "connected_cases_count": len(cases_linked),
                "associates_count": associate_count,
                "jurisdictions_count": len(jurisdictions),
                "jurisdictions": list(jurisdictions),
                "centrality_metrics": node_cent,
                "xai_breakdown": {
                    "network_centrality_contribution": round(network_score, 1),
                    "case_severity_contribution": round(case_score, 1),
                    "jurisdiction_spread_contribution": round(jurisdiction_score, 1),
                    "associate_asset_contribution": round(asset_score, 1),
                    "severity_reasons": severity_reasons[:4]
                }
            })

        # Sort descending by risk score
        ranked_persons.sort(key=lambda x: x["risk_score"], reverse=True)
        return ranked_persons

    def detect_communities(self) -> Dict[str, Any]:
        """
        Performs Louvain Community Detection to discover operational crime cells / gangs.
        Returns partition mapping and modularity score.
        """
        if len(self.engine.graph) < 2:
            return {"communities": [], "modularity": 0.0, "total_communities": 0}

        G_undirected = self._get_undirected_view()
        
        try:
            # Louvain partition
            communities_sets = nx.community.louvain_communities(G_undirected, seed=42)
            modularity = nx.community.modularity(G_undirected, communities_sets)
        except Exception:
            # Fallback to connected components
            communities_sets = list(nx.connected_components(G_undirected))
            modularity = 0.0

        community_list = []
        node_to_comm = {}

        # Colors for front-end rendering
        cluster_colors = [
            "#3B82F6", "#EC4899", "#10B981", "#F59E0B", 
            "#8B5CF6", "#06B6D4", "#EF4444", "#84CC16", 
            "#F97316", "#14B8A6"
        ]

        for i, c_set in enumerate(communities_sets):
            comm_id = f"cell_{i+1}"
            color = cluster_colors[i % len(cluster_colors)]
            
            nodes_in_comm = [self.engine.nodes_data[nid] for nid in c_set if nid in self.engine.nodes_data]
            
            # Find key hub / kingpin inside this cell
            persons_in_comm = [n for n in nodes_in_comm if n.get("label") == "Person"]
            key_leader = max(persons_in_comm, key=lambda x: x.get("risk_score", 0.0)) if persons_in_comm else None

            # Detect main crime focus
            case_categories = [
                n.get("crime_category") for n in nodes_in_comm 
                if n.get("label") == "Case" and n.get("crime_category")
            ]
            primary_focus = max(set(case_categories), key=case_categories.count) if case_categories else "General Criminal Syndicate"

            comm_info = {
                "community_id": comm_id,
                "label": f"Gang / Syndicate Module #{i+1}",
                "color": color,
                "primary_focus": primary_focus,
                "total_members": len(nodes_in_comm),
                "person_count": len(persons_in_comm),
                "leader_candidate": {
                    "id": key_leader["id"],
                    "name": key_leader["name"],
                    "risk_score": key_leader.get("risk_score", 0.0)
                } if key_leader else None,
                "node_ids": list(c_set)
            }
            community_list.append(comm_info)

            for nid in c_set:
                node_to_comm[nid] = {
                    "community_id": comm_id,
                    "color": color,
                    "community_name": comm_info["label"]
                }
                # Assign to node data
                if nid in self.engine.nodes_data:
                    self.engine.nodes_data[nid]["community_id"] = comm_id
                    self.engine.nodes_data[nid]["community_color"] = color

        return {
            "communities": community_list,
            "modularity_score": round(modularity, 4),
            "total_communities": len(community_list),
            "node_partition_map": node_to_comm
        }

    def find_shortest_path(self, source_id: str, target_id: str) -> Dict[str, Any]:
        """
        Finds the shortest relational chain connecting two entities (Cypher shortestPath equivalent).
        Explains the multi-hop connection link-by-link.
        """
        source_id = str(source_id)
        target_id = str(target_id)

        if source_id not in self.engine.graph or target_id not in self.engine.graph:
            return {"found": False, "message": "Source or target entity not found in graph."}

        G_undirected = self._get_undirected_view()

        try:
            path_node_ids = nx.shortest_path(G_undirected, source=source_id, target=target_id)
        except nx.NetworkXNoPath:
            return {
                "found": False,
                "source_id": source_id,
                "target_id": target_id,
                "message": "No direct or indirect connection found between these two entities."
            }

        # Build path steps
        path_nodes = [self.engine.nodes_data[nid] for nid in path_node_ids if nid in self.engine.nodes_data]
        
        path_edges = []
        step_explanations = []

        for idx in range(len(path_node_ids) - 1):
            u = path_node_ids[idx]
            v = path_node_ids[idx + 1]
            u_node = self.engine.nodes_data.get(u, {})
            v_node = self.engine.nodes_data.get(v, {})

            # Find connecting edge data
            matched_edges = [
                e for e in self.engine.edges_data.values()
                if (e["source"] == u and e["target"] == v) or (e["source"] == v and e["target"] == u)
            ]
            rel_type = matched_edges[0].get("relation_type", "CONNECTED_TO") if matched_edges else "LINKED"
            
            path_edges.append(matched_edges[0] if matched_edges else {
                "source": u, "target": v, "relation_type": rel_type
            })

            step_explanations.append({
                "step": idx + 1,
                "from_entity": f"{u_node.get('name')} ({u_node.get('label')})",
                "relation": rel_type,
                "to_entity": f"{v_node.get('name')} ({v_node.get('label')})",
                "detail": f"{u_node.get('name')} is connected to {v_node.get('name')} via {rel_type}."
            })

        return {
            "found": True,
            "hop_distance": len(path_node_ids) - 1,
            "path_node_ids": path_node_ids,
            "nodes": path_nodes,
            "edges": path_edges,
            "step_explanations": step_explanations
        }

    def detect_cross_jurisdiction_links(self) -> List[Dict[str, Any]]:
        """
        Detects entities (Suspects, Phones, Financial Accounts, Vehicles) that appear
        in cases filed across different police stations / states (OCND / CCTNS flagship use case).
        """
        cross_links = []
        
        # Check all non-case nodes to see which cases they link to
        for node_id, node in self.engine.nodes_data.items():
            if node.get("label") == "Case":
                continue

            neighbors = self.engine.get_neighbors(node_id, direction="both")
            linked_cases = [nb["node"] for nb in neighbors if nb["node"].get("label") == "Case"]

            if len(linked_cases) > 1:
                # Check if jurisdictions / stations differ
                stations = list({c.get("station") for c in linked_cases if c.get("station")})
                states = list({c.get("state") for c in linked_cases if c.get("state")})
                jurisdiction_codes = list({c.get("jurisdiction_code") for c in linked_cases if c.get("jurisdiction_code")})

                if len(stations) > 1 or len(jurisdiction_codes) > 1:
                    cross_links.append({
                        "entity_id": node_id,
                        "entity_label": node.get("label"),
                        "entity_name": node.get("name"),
                        "risk_score": node.get("risk_score", 0.0),
                        "jurisdictions_involved": jurisdiction_codes,
                        "stations_involved": stations,
                        "states_involved": states,
                        "case_count": len(linked_cases),
                        "cases": [{
                            "case_id": c.get("case_id"),
                            "fir_number": c.get("fir_number"),
                            "station": c.get("station"),
                            "state": c.get("state"),
                            "crime_category": c.get("crime_category"),
                            "filed_date": c.get("filed_date")
                        } for c in linked_cases],
                        "alert_level": "CRITICAL" if len(states) > 1 else "HIGH",
                        "summary": f"{node.get('label')} '{node.get('name')}' links {len(linked_cases)} independent FIRs across {len(stations)} jurisdictions ({', '.join(stations)})."
                    })

        # Sort by case count and risk score
        cross_links.sort(key=lambda x: (x["case_count"], x["risk_score"]), reverse=True)
        return cross_links
