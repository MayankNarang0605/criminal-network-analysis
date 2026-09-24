"""
Graph intelligence engine.

Projects the relational store into an in-process NetworkX multigraph and runs the
network analysis that the problem statement asks for: relationship maps, key-actor
identification, community detection, shortest paths between suspects, and link
prediction for unobserved relationships.

Why in-process instead of Neo4j: at the data volumes an investigating unit works
with per case cluster (10^3–10^5 entities), NetworkX in memory is faster than a
Bolt round trip, and it removes the single biggest deployment obstacle in a police
network. `GraphEngine.load()` is the only place that touches storage, so pointing
this at Neo4j is a localised change.
"""
from __future__ import annotations

import math
from collections import defaultdict
from functools import lru_cache
from typing import Any, Iterable

import networkx as nx

from app import db
from app.config import settings

# Relationship types that represent operational (dirty-work) proximity. Used by
# the insulation index: bosses are structurally distant from these.
OPERATIONAL_RELS = {
    "USES_VEHICLE", "USES_PHONE", "CARRIED", "TRANSPORTED", "COURIER_FOR",
    "SEIZED_FROM", "PRESENT_AT",
}

# Edge weights by semantic strength. Co-accused in the same FIR is much stronger
# evidence of association than mere co-mention in a report.
REL_STRENGTH = {
    "CO_ACCUSED": 1.0,
    "CONSPIRED_WITH": 1.0,
    "DIRECTS": 0.95,
    "REPORTS_TO": 0.95,
    "ASSOCIATE_OF": 0.8,
    "CALLED": 0.7,
    "TRANSFERRED_TO": 0.85,
    "RECRUITED_BY": 0.85,
    "WORKS_FOR": 0.8,
    "OPERATES_FOR": 0.7,
    "MET_WITH": 0.6,
    "LINKED_TO": 0.55,
    "CO_MENTIONED": 0.35,
    "SHARED_TOWER": 0.5,
    "SHARED_ACCOUNT": 0.75,
    "SHARED_VEHICLE": 0.7,
}


class GraphEngine:
    """Loads and analyses the entity relationship graph."""

    def __init__(self) -> None:
        self.G: nx.Graph = nx.Graph()
        self.DG: nx.DiGraph = nx.DiGraph()
        self._version = 0
        self._metrics_cache: dict[str, dict[str, float]] = {}
        self._communities: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load(self) -> "GraphEngine":
        """(Re)build the in-memory graph from the store."""
        self.G = nx.Graph()
        self.DG = nx.DiGraph()

        for row in db.query(
            "SELECT entity_id, type, name, aliases, attributes, risk_score, "
            "kingpin_score, source_count FROM entities"
        ):
            attrs = db.jload(row["attributes"], {})
            self.G.add_node(
                row["entity_id"],
                label=row["name"],
                type=row["type"],
                risk_score=row["risk_score"] or 0.0,
                kingpin_score=row["kingpin_score"] or 0.0,
                source_count=row["source_count"] or 0,
                aliases=db.jload(row["aliases"], []),
                **{k: v for k, v in attrs.items() if isinstance(v, (str, int, float, bool))},
            )

        for row in db.query(
            "SELECT source_id, target_id, rel_type, weight, confidence, "
            "observations, evidence, attributes FROM relationships"
        ):
            s, t = row["source_id"], row["target_id"]
            if s == t or s not in self.G or t not in self.G:
                continue
            rel = row["rel_type"]
            strength = REL_STRENGTH.get(rel, 0.5)
            weight = float(row["weight"] or 1.0) * strength * float(row["confidence"] or 1.0)

            if self.G.has_edge(s, t):
                data = self.G[s][t]
                data["weight"] = data.get("weight", 0.0) + weight
                data["rel_types"] = sorted(set(data.get("rel_types", [])) | {rel})
                data["observations"] = data.get("observations", 0) + int(row["observations"] or 1)
                data["confidence"] = max(data.get("confidence", 0.0), float(row["confidence"] or 1.0))
            else:
                self.G.add_edge(
                    s, t,
                    weight=weight,
                    rel_types=[rel],
                    rel_type=rel,
                    confidence=float(row["confidence"] or 1.0),
                    observations=int(row["observations"] or 1),
                )
            self.DG.add_edge(s, t, rel_type=rel, weight=weight)

        self._version += 1
        self._metrics_cache = {}
        self._communities = {}
        return self

    @property
    def loaded(self) -> bool:
        return self.G.number_of_nodes() > 0

    def ensure(self) -> "GraphEngine":
        if not self.loaded:
            self.load()
        return self

    def person_subgraph(self) -> nx.Graph:
        """Person-only projection: the actual social network of the syndicate."""
        people = [n for n, d in self.G.nodes(data=True) if d.get("type") == "Person"]
        return self.G.subgraph(people).copy()

    # ------------------------------------------------------------------
    # Centrality
    # ------------------------------------------------------------------
    def centrality(self, person_only: bool = True) -> dict[str, dict[str, float]]:
        """
        Compute the standard influence measures plus weighted variants.
        Cached per graph version because betweenness is the expensive one.
        """
        cache_key = f"cent:{person_only}:{self._version}"
        if cache_key in self._metrics_cache:
            return self._metrics_cache[cache_key]

        g = self.person_subgraph() if person_only else self.G
        if g.number_of_nodes() == 0:
            return {}

        # Distance = inverse strength, so strong ties are "short" for path metrics.
        dist = {(u, v): 1.0 / max(d.get("weight", 0.1), 0.01)
                for u, v, d in g.edges(data=True)}
        nx.set_edge_attributes(g, {k: {"distance": v} for k, v in dist.items()})

        n = g.number_of_nodes()
        k = None if n <= 400 else 400   # sampled betweenness on large graphs

        degree = dict(g.degree())
        strength = {node: sum(d.get("weight", 0.0) for _, _, d in g.edges(node, data=True))
                    for node in g.nodes()}
        betweenness = nx.betweenness_centrality(g, k=k, weight="distance", normalized=True, seed=42)
        closeness = nx.closeness_centrality(g, distance="distance")
        try:
            eigenvector = nx.eigenvector_centrality(g, max_iter=1000, tol=1e-6, weight="weight")
        except (nx.PowerIterationFailedConvergence, nx.NetworkXException):
            eigenvector = {node: 0.0 for node in g.nodes()}
        pagerank = nx.pagerank(g, alpha=0.85, weight="weight")
        try:
            clustering = nx.clustering(g, weight="weight")
        except Exception:
            clustering = {node: 0.0 for node in g.nodes()}
        core = nx.core_number(g) if g.number_of_edges() else {node: 0 for node in g.nodes()}

        # Articulation points: removal disconnects the network (broker signature).
        articulation = set(nx.articulation_points(g)) if g.number_of_edges() else set()

        max_deg = max(degree.values()) or 1
        max_strength = max(strength.values()) or 1.0
        max_core = max(core.values()) or 1

        out: dict[str, dict[str, float]] = {}
        for node in g.nodes():
            out[node] = {
                "degree": degree.get(node, 0),
                "degree_norm": degree.get(node, 0) / max_deg,
                "strength": round(strength.get(node, 0.0), 4),
                "strength_norm": strength.get(node, 0.0) / max_strength,
                "betweenness": round(betweenness.get(node, 0.0), 6),
                "closeness": round(closeness.get(node, 0.0), 6),
                "eigenvector": round(eigenvector.get(node, 0.0), 6),
                "pagerank": round(pagerank.get(node, 0.0), 6),
                "clustering": round(clustering.get(node, 0.0), 4),
                "k_core": core.get(node, 0),
                "k_core_norm": core.get(node, 0) / max_core,
                "is_articulation_point": node in articulation,
            }
        self._metrics_cache[cache_key] = out
        return out

    # ------------------------------------------------------------------
    # Community detection
    # ------------------------------------------------------------------
    def communities(self, resolution: float = 1.0, person_only: bool = True) -> dict[str, Any]:
        """
        Louvain modularity communities = candidate criminal cells/modules.
        Falls back to greedy modularity if Louvain is unavailable.
        """
        g = self.person_subgraph() if person_only else self.G
        if g.number_of_nodes() == 0:
            return {"communities": [], "modularity": 0.0, "assignment": {}}

        try:
            comms = nx.community.louvain_communities(
                g, weight="weight", resolution=resolution, seed=42
            )
        except Exception:
            comms = list(nx.community.greedy_modularity_communities(g, weight="weight"))

        comms = sorted((sorted(c) for c in comms), key=len, reverse=True)
        try:
            modularity = nx.community.modularity(g, comms, weight="weight")
        except Exception:
            modularity = 0.0

        assignment: dict[str, int] = {}
        payload: list[dict] = []
        for cid, members in enumerate(comms):
            for m in members:
                assignment[m] = cid
            sub = g.subgraph(members)
            internal = sub.number_of_edges()
            possible = len(members) * (len(members) - 1) / 2 or 1
            external = sum(
                1 for m in members for nb in g.neighbors(m) if nb not in set(members)
            )
            payload.append({
                "community_id": cid,
                "size": len(members),
                "members": members,
                "density": round(internal / possible, 4),
                "internal_edges": internal,
                "external_edges": external,
                # High cohesion + low external = tight, insular cell.
                "insularity": round(internal / (internal + external) if (internal + external) else 0.0, 4),
                "avg_risk": round(
                    sum(self.G.nodes[m].get("risk_score", 0.0) for m in members) / len(members), 2
                ),
            })

        self._communities = assignment
        return {
            "communities": payload,
            "modularity": round(modularity, 4),
            "count": len(payload),
            "assignment": assignment,
        }

    # ------------------------------------------------------------------
    # Kingpin identification
    # ------------------------------------------------------------------
    def insulation_index(self) -> dict[str, float]:
        """
        Insulation = how far an actor sits from the operational layer.

        Leaders in real syndicates rarely touch the contraband, the vehicle, or
        the victim. They are highly connected but their neighbours are the ones
        with operational edges. This computes, per actor, the fraction of its
        neighbourhood that carries operational evidence while the actor itself
        does not — the structural signature of command.

        This is what conventional centrality misses, and it is the reason a
        courier with 30 calls does not outrank a boss with 6.
        """
        g = self.person_subgraph()
        operational_load: dict[str, float] = {}
        for node in g.nodes():
            load = 0.0
            for nb in self.G.neighbors(node):
                ntype = self.G.nodes[nb].get("type")
                rels = set(self.G[node][nb].get("rel_types", []))
                if ntype in ("Vehicle", "Location", "Event") or (rels & OPERATIONAL_RELS):
                    load += 1.0
            operational_load[node] = load

        max_load = max(operational_load.values(), default=0.0) or 1.0
        norm_load = {k: v / max_load for k, v in operational_load.items()}

        out: dict[str, float] = {}
        for node in g.nodes():
            neighbours = list(g.neighbors(node))
            if not neighbours:
                out[node] = 0.0
                continue
            nb_load = sum(norm_load.get(nb, 0.0) for nb in neighbours) / len(neighbours)
            own_load = norm_load.get(node, 0.0)
            # Subordinates carry the operational load; the actor does not.
            insulation = nb_load - own_load
            # Weight by reach: insulation only signals command if you have span.
            span = min(len(neighbours) / 6.0, 1.0)
            out[node] = round(max(0.0, insulation) * span, 4)
        return out

    def flow_control(self) -> dict[str, float]:
        """
        Share of network money/communication volume that passes through an actor.
        Uses current-flow (electrical) betweenness where possible, which models
        parallel routes better than shortest-path betweenness for money flows.
        """
        g = self.person_subgraph()
        if g.number_of_edges() == 0:
            return {n: 0.0 for n in g.nodes()}
        # Current-flow betweenness requires a connected graph; run per component.
        out: dict[str, float] = {}
        for component in nx.connected_components(g):
            sub = g.subgraph(component)
            if sub.number_of_nodes() < 3:
                for n in sub.nodes():
                    out[n] = 0.0
                continue
            try:
                cfb = nx.current_flow_betweenness_centrality(sub, weight="weight", normalized=True)
            except Exception:
                cfb = nx.betweenness_centrality(sub, weight="weight", normalized=True)
            # Scale by component size so a 3-node component cannot dominate.
            scale = sub.number_of_nodes() / g.number_of_nodes()
            for n, v in cfb.items():
                out[n] = round(v * (0.4 + 0.6 * scale), 6)
        return out

    def role_breadth(self) -> dict[str, float]:
        """How many distinct crime domains / relationship types an actor spans."""
        out: dict[str, float] = {}
        domains_by_entity: dict[str, set[str]] = defaultdict(set)
        for row in db.query(
            "SELECT ec.entity_id, c.crime_type FROM entity_cases ec "
            "JOIN cases c ON c.fir_id = ec.fir_id"
        ):
            if row["crime_type"]:
                domains_by_entity[row["entity_id"]].add(row["crime_type"])

        g = self.person_subgraph()
        for node in g.nodes():
            rel_types: set[str] = set()
            for nb in self.G.neighbors(node):
                rel_types |= set(self.G[node][nb].get("rel_types", []))
            domains = len(domains_by_entity.get(node, set()))
            out[node] = round(min(domains / 3.0, 1.0) * 0.6 + min(len(rel_types) / 6.0, 1.0) * 0.4, 4)
        return out

    def resilience_impact(self) -> dict[str, float]:
        """
        Fraction of network cohesion lost if the actor is removed.
        Measured as drop in the largest-connected-component share plus the
        increase in average path length. This is the operational question a
        commander actually asks: "who do we arrest to break this network?"
        """
        g = self.person_subgraph()
        n = g.number_of_nodes()
        if n < 3:
            return {node: 0.0 for node in g.nodes()}

        base_lcc = len(max(nx.connected_components(g), key=len)) / n
        base_pairs = _reachable_pair_fraction(g)

        out: dict[str, float] = {}
        for node in g.nodes():
            h = g.copy()
            h.remove_node(node)
            if h.number_of_nodes() == 0:
                out[node] = 1.0
                continue
            lcc = len(max(nx.connected_components(h), key=len)) / h.number_of_nodes()
            pairs = _reachable_pair_fraction(h)
            damage = max(0.0, base_lcc - lcc) * 0.5 + max(0.0, base_pairs - pairs) * 0.5
            out[node] = round(min(damage * 2.5, 1.0), 4)
        return out

    def kingpin_ranking(self, top_n: int = 20) -> list[dict]:
        """
        Composite Kingpin Influence Score (0–100) with per-factor attribution.

        Combines six orthogonal signals rather than a single centrality, because
        any one measure is trivially gamed by data artefacts: a call-centre number
        has huge degree, a courier has huge betweenness on a linear route. The
        insulation and resilience terms are what separate command from volume.
        """
        cent = self.centrality(person_only=True)
        if not cent:
            return []

        insulation = self.insulation_index()
        flow = self.flow_control()
        breadth = self.role_breadth()
        resilience = self.resilience_impact()

        raw = {
            "betweenness": {k: v["betweenness"] for k, v in cent.items()},
            "eigenvector": {k: v["eigenvector"] for k, v in cent.items()},
            "insulation": insulation,
            "flow_control": flow,
            "role_breadth": breadth,
            "resilience": resilience,
        }
        normed = {name: _normalize(values) for name, values in raw.items()}
        weights = settings.KINGPIN_WEIGHTS

        results: list[dict] = []
        for node in cent:
            contributions = {
                factor: round(weights[factor] * normed[factor].get(node, 0.0) * 100, 2)
                for factor in weights
            }
            score = round(sum(contributions.values()), 2)
            node_data = self.G.nodes[node]
            drivers = sorted(contributions.items(), key=lambda kv: -kv[1])[:3]
            results.append({
                "entity_id": node,
                "name": node_data.get("label", node),
                "type": node_data.get("type"),
                "kingpin_score": score,
                "tier": _tier(score),
                "contributions": contributions,
                "primary_drivers": [d[0] for d in drivers],
                "explanation": _explain_kingpin(node_data.get("label", node), contributions,
                                                cent[node], insulation.get(node, 0.0)),
                "metrics": cent[node],
                "insulation_index": insulation.get(node, 0.0),
                "network_damage_if_removed": resilience.get(node, 0.0),
                "community_id": self._communities.get(node),
                "risk_score": node_data.get("risk_score", 0.0),
            })

        results.sort(key=lambda r: -r["kingpin_score"])
        for rank, item in enumerate(results, start=1):
            item["rank"] = rank
        return results[:top_n] if top_n else results

    # ------------------------------------------------------------------
    # Paths and neighbourhoods
    # ------------------------------------------------------------------
    def shortest_paths(self, source: str, target: str, k: int = 3) -> list[dict]:
        """Up to k shortest weighted paths — 'how is A connected to B'."""
        if source not in self.G or target not in self.G:
            return []
        g = self.G
        for u, v, d in g.edges(data=True):
            d["distance"] = 1.0 / max(d.get("weight", 0.1), 0.01)
        try:
            gen = nx.shortest_simple_paths(g, source, target, weight="distance")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
        paths: list[dict] = []
        for idx, path in enumerate(gen):
            if idx >= k:
                break
            hops = []
            total_conf = 1.0
            for a, b in zip(path, path[1:]):
                data = g[a][b]
                conf = data.get("confidence", 1.0)
                total_conf *= conf
                hops.append({
                    "from": a, "from_name": g.nodes[a].get("label", a),
                    "to": b, "to_name": g.nodes[b].get("label", b),
                    "rel_types": data.get("rel_types", []),
                    "weight": round(data.get("weight", 0.0), 3),
                    "confidence": round(conf, 3),
                })
            paths.append({
                "path": path,
                "names": [g.nodes[p].get("label", p) for p in path],
                "length": len(path) - 1,
                "hops": hops,
                "path_confidence": round(total_conf, 4),
                "narrative": _path_narrative(g, path),
            })
        return paths

    def neighbourhood(self, entity_id: str, depth: int = 1, limit: int = 200) -> dict:
        """Ego network for the graph explorer."""
        if entity_id not in self.G:
            return {"nodes": [], "edges": []}
        nodes = {entity_id}
        frontier = {entity_id}
        for _ in range(max(1, depth)):
            nxt: set[str] = set()
            for node in frontier:
                for nb in self.G.neighbors(node):
                    if nb not in nodes:
                        nxt.add(nb)
            nodes |= nxt
            frontier = nxt
            if len(nodes) >= limit:
                break
        sub = self.G.subgraph(list(nodes)[:limit])
        return self.to_payload(sub, focus=entity_id)

    def to_payload(self, g: nx.Graph | None = None, focus: str | None = None) -> dict:
        """Serialise a graph for the frontend visualiser."""
        g = self.G if g is None else g
        nodes = []
        for n, d in g.nodes(data=True):
            nodes.append({
                "id": n,
                "label": d.get("label", n),
                "type": d.get("type", "Unknown"),
                "risk_score": round(d.get("risk_score", 0.0), 1),
                "kingpin_score": round(d.get("kingpin_score", 0.0), 1),
                "degree": g.degree(n),
                "community_id": self._communities.get(n),
                "is_focus": n == focus,
            })
        edges = []
        for u, v, d in g.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "rel_type": (d.get("rel_types") or [d.get("rel_type", "RELATED_TO")])[0],
                "rel_types": d.get("rel_types", []),
                "weight": round(d.get("weight", 1.0), 3),
                "confidence": round(d.get("confidence", 1.0), 3),
                "observations": d.get("observations", 1),
            })
        return {"nodes": nodes, "edges": edges,
                "stats": {"node_count": len(nodes), "edge_count": len(edges)}}

    # ------------------------------------------------------------------
    # Link prediction
    # ------------------------------------------------------------------
    def predict_links(self, top_n: int = 25, min_score: float = 0.15) -> list[dict]:
        """
        Predict unobserved relationships — the 'hidden connections' requirement.

        Ensemble of Adamic-Adar (rare shared associates matter more), Jaccard
        (neighbourhood overlap), preferential attachment (hub affinity), and a
        same-community bonus. Scores are calibrated to 0–1 and every prediction
        carries the shared intermediaries as its justification, so an investigator
        can verify it rather than trust it.
        """
        g = self.person_subgraph()
        if g.number_of_nodes() < 3:
            return []
        if not self._communities:
            self.communities()

        candidates = [
            (u, v) for u, v in nx.non_edges(g)
            if len(set(g.neighbors(u)) & set(g.neighbors(v))) >= 1
        ]
        if not candidates:
            return []

        aa = {(u, v): s for u, v, s in nx.adamic_adar_index(g, candidates)}
        jc = {(u, v): s for u, v, s in nx.jaccard_coefficient(g, candidates)}
        pa = {(u, v): s for u, v, s in nx.preferential_attachment(g, candidates)}
        max_aa = max(aa.values(), default=1.0) or 1.0
        max_pa = max(pa.values(), default=1.0) or 1.0

        out: list[dict] = []
        for pair in candidates:
            u, v = pair
            shared = sorted(set(g.neighbors(u)) & set(g.neighbors(v)))
            same_comm = self._communities.get(u) is not None and \
                self._communities.get(u) == self._communities.get(v)
            score = (
                0.40 * (aa.get(pair, 0.0) / max_aa)
                + 0.25 * jc.get(pair, 0.0)
                + 0.15 * (pa.get(pair, 0.0) / max_pa)
                + 0.20 * (1.0 if same_comm else 0.0)
            )
            if score < min_score:
                continue
            out.append({
                "source": u,
                "source_name": g.nodes[u].get("label", u),
                "target": v,
                "target_name": g.nodes[v].get("label", v),
                "probability": round(min(score, 0.99), 4),
                "confidence_band": "high" if score > 0.6 else "medium" if score > 0.35 else "low",
                "shared_associates": [g.nodes[s].get("label", s) for s in shared],
                "shared_count": len(shared),
                "same_community": same_comm,
                "signals": {
                    "adamic_adar": round(aa.get(pair, 0.0), 4),
                    "jaccard": round(jc.get(pair, 0.0), 4),
                    "preferential_attachment": int(pa.get(pair, 0.0)),
                },
                "rationale": (
                    f"{g.nodes[u].get('label', u)} and {g.nodes[v].get('label', v)} share "
                    f"{len(shared)} common associate(s) "
                    f"({', '.join(g.nodes[s].get('label', s) for s in shared[:3])})"
                    + (" and belong to the same detected cell" if same_comm else "")
                    + " but no direct link is recorded — recommend targeted verification."
                ),
            })
        out.sort(key=lambda d: -d["probability"])
        return out[:top_n]

    # ------------------------------------------------------------------
    # Disruption simulation
    # ------------------------------------------------------------------
    def simulate_disruption(self, targets: list[str]) -> dict:
        """
        'If we arrest these people, what happens to the network?'

        Reports fragmentation, largest remaining cell, isolated actors, and which
        successor is likely to take over (highest kingpin score among survivors).
        This turns analysis into an actionable operational recommendation.
        """
        g = self.person_subgraph()
        if g.number_of_nodes() == 0:
            return {"error": "graph is empty"}

        valid = [t for t in targets if t in g]
        before = {
            "nodes": g.number_of_nodes(),
            "edges": g.number_of_edges(),
            "components": nx.number_connected_components(g),
            "largest_component": len(max(nx.connected_components(g), key=len)),
            "reachable_pair_fraction": round(_reachable_pair_fraction(g), 4),
            "avg_degree": round(2 * g.number_of_edges() / max(g.number_of_nodes(), 1), 2),
        }

        h = g.copy()
        h.remove_nodes_from(valid)
        if h.number_of_nodes() == 0:
            after = {"nodes": 0, "edges": 0, "components": 0, "largest_component": 0,
                     "reachable_pair_fraction": 0.0, "avg_degree": 0.0}
        else:
            after = {
                "nodes": h.number_of_nodes(),
                "edges": h.number_of_edges(),
                "components": nx.number_connected_components(h),
                "largest_component": len(max(nx.connected_components(h), key=len)),
                "reachable_pair_fraction": round(_reachable_pair_fraction(h), 4),
                "avg_degree": round(2 * h.number_of_edges() / max(h.number_of_nodes(), 1), 2),
            }

        isolated = [n for n in h.nodes() if h.degree(n) == 0]
        fragmentation = (
            round((1 - after["reachable_pair_fraction"] / before["reachable_pair_fraction"]) * 100, 2)
            if before["reachable_pair_fraction"] else 0.0
        )

        # Likely successor: rank survivors on the same composite score.
        survivors = [k for k in self.kingpin_ranking(top_n=0) if k["entity_id"] in h]
        successor = survivors[0] if survivors else None

        return {
            "targets": [{"entity_id": t, "name": g.nodes[t].get("label", t)} for t in valid],
            "invalid_targets": [t for t in targets if t not in g],
            "before": before,
            "after": after,
            "impact": {
                "fragmentation_pct": max(fragmentation, 0.0),
                "edges_removed": before["edges"] - after["edges"],
                "edges_removed_pct": round(
                    (before["edges"] - after["edges"]) / max(before["edges"], 1) * 100, 2),
                "new_components": after["components"] - before["components"],
                "isolated_actors": [{"entity_id": n, "name": g.nodes[n].get("label", n)}
                                    for n in isolated],
                "largest_cell_reduction_pct": round(
                    (before["largest_component"] - after["largest_component"])
                    / max(before["largest_component"], 1) * 100, 2),
            },
            "likely_successor": {
                "entity_id": successor["entity_id"],
                "name": successor["name"],
                "kingpin_score": successor["kingpin_score"],
            } if successor else None,
            "assessment": _disruption_assessment(fragmentation, len(isolated)),
        }

    def optimal_disruption(self, budget: int = 3) -> dict:
        """
        Greedy selection of the arrest set that maximises fragmentation for a
        given number of arrests. Greedy is near-optimal for this submodular
        objective and, unlike exhaustive search, it stays tractable.
        """
        g = self.person_subgraph()
        chosen: list[str] = []
        working = g.copy()
        trace: list[dict] = []

        for step in range(max(1, budget)):
            if working.number_of_nodes() <= 1:
                break
            best_node, best_damage = None, -1.0
            base_pairs = _reachable_pair_fraction(working)
            for node in working.nodes():
                h = working.copy()
                h.remove_node(node)
                damage = base_pairs - _reachable_pair_fraction(h) if h.number_of_nodes() else 1.0
                if damage > best_damage:
                    best_node, best_damage = node, damage
            if best_node is None:
                break
            chosen.append(best_node)
            working.remove_node(best_node)
            trace.append({
                "step": step + 1,
                "entity_id": best_node,
                "name": g.nodes[best_node].get("label", best_node),
                "marginal_fragmentation": round(max(best_damage, 0.0) * 100, 2),
            })

        return {
            "budget": budget,
            "recommended_arrests": trace,
            "simulation": self.simulate_disruption(chosen),
        }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if math.isclose(hi, lo):
        return {k: 0.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def _reachable_pair_fraction(g: nx.Graph) -> float:
    """Fraction of node pairs that remain mutually reachable."""
    n = g.number_of_nodes()
    if n < 2:
        return 0.0
    total = n * (n - 1) / 2
    reachable = sum(len(c) * (len(c) - 1) / 2 for c in nx.connected_components(g))
    return reachable / total


def _tier(score: float) -> str:
    if score >= 60:
        return "Tier-1 (Command)"
    if score >= 40:
        return "Tier-2 (Coordination)"
    if score >= 22:
        return "Tier-3 (Operational)"
    return "Tier-4 (Peripheral)"


def _explain_kingpin(name: str, contributions: dict[str, float],
                     metrics: dict[str, float], insulation: float) -> str:
    top = sorted(contributions.items(), key=lambda kv: -kv[1])[:2]
    phrases = {
        "betweenness": "sits on the majority of communication and money routes between subgroups",
        "eigenvector": "is directly connected to other high-influence actors",
        "insulation": "stays structurally removed from operational activity while directing those who perform it",
        "flow_control": "controls a disproportionate share of network flow volume",
        "role_breadth": "operates across multiple crime domains simultaneously",
        "resilience": "holds the network together — removal causes measurable fragmentation",
    }
    reasons = "; ".join(phrases.get(f, f) for f, _ in top)
    extra = ""
    if metrics.get("is_articulation_point"):
        extra = " Removal alone splits the network into disconnected cells (articulation point)."
    if insulation > 0.35:
        extra += (f" Insulation index {insulation:.2f} indicates a command role rather than"
                  " a hands-on operative.")
    return f"{name} {reasons}.{extra}"


def _path_narrative(g: nx.Graph, path: list[str]) -> str:
    parts = []
    for a, b in zip(path, path[1:]):
        rel = (g[a][b].get("rel_types") or ["linked to"])[0].replace("_", " ").lower()
        parts.append(f"{g.nodes[a].get('label', a)} —[{rel}]→ {g.nodes[b].get('label', b)}")
    return " ; ".join(parts)


def _disruption_assessment(fragmentation: float, isolated: int) -> str:
    if fragmentation >= 50:
        verdict = "High-impact intervention: the network loses over half its internal reachability."
    elif fragmentation >= 20:
        verdict = "Moderate impact: significant coordination capacity is lost but the core survives."
    elif fragmentation > 0:
        verdict = "Low impact: the network is resilient to this arrest set and will re-route."
    else:
        verdict = "Negligible structural impact — these actors are replaceable within the network."
    if isolated:
        verdict += f" {isolated} actor(s) become fully isolated and lose operational support."
    return verdict


# Module-level singleton used by the routers.
engine = GraphEngine()
