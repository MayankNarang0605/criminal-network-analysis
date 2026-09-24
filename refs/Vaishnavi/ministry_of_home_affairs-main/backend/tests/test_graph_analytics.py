"""
Unit Tests for Graph Analytics, Centrality, Community Detection, Shortest Path & Link Prediction
"""

from backend.app.graph.engine import CriminalGraphEngine
from backend.app.graph.analytics import GraphAnalytics
from backend.app.graph.link_prediction import LinkPredictor

def test_graph_algorithms():
    engine = CriminalGraphEngine(persistence_path=None)
    engine.clear()

    # Create small test network
    # P1 (Kingpin) -> P2 (Broker) -> P3 (Mule)
    # P1 -> P4 (Associate)
    # P2 -> P4
    engine.add_node("P1", "Person", "Suspect Alpha", {"status": "Kingpin"})
    engine.add_node("P2", "Person", "Suspect Beta", {"status": "Broker"})
    engine.add_node("P3", "Person", "Suspect Gamma", {"status": "Mule"})
    engine.add_node("P4", "Person", "Suspect Delta", {"status": "Associate"})
    engine.add_node("C1", "Case", "FIR 101", {"crime_category": "Cyber Fraud & Phishing", "jurisdiction_code": "DL-POLICE-SPL"})

    engine.add_edge("P1", "P2", "ASSOCIATE_OF")
    engine.add_edge("P2", "P3", "ASSOCIATE_OF")
    engine.add_edge("P1", "P4", "ASSOCIATE_OF")
    engine.add_edge("P2", "P4", "ASSOCIATE_OF")
    engine.add_edge("P1", "C1", "ACCUSED_IN")

    analytics = GraphAnalytics(engine)

    # 1. Centralities
    centralities = analytics.compute_centrality_metrics()
    assert "P1" in centralities
    assert "P2" in centralities
    assert centralities["P2"]["betweenness_centrality"] >= 0.0

    # 2. Shortest Path
    path_res = analytics.find_shortest_path("P1", "P3")
    assert path_res["found"] is True
    assert path_res["path_node_ids"] == ["P1", "P2", "P3"]
    assert path_res["hop_distance"] == 2

    # 3. Community Detection
    comm_res = analytics.detect_communities()
    assert comm_res["total_communities"] >= 1

    # 4. Link Prediction
    predictor = LinkPredictor(engine)
    # P3 and P4 do not have direct edge, but both connect to P2
    predictions = predictor.predict_missing_links(top_k=5, min_score=0.1)
    assert len(predictions) >= 1
    assert any((p["source_id"] in ("P3", "P4") and p["target_id"] in ("P3", "P4")) for p in predictions)

    print("✓ Graph analytics, shortest path, and link prediction tests passed!")

if __name__ == "__main__":
    test_graph_algorithms()
