"""
Full API Integration Test against live server at http://127.0.0.1:8000
"""

import urllib.request
import urllib.parse
import json

BASE_URL = "http://127.0.0.1:8000"

def make_request(path, method="GET", body=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "application/json" in content_type:
                return resp.status, json.loads(raw.decode("utf-8"))
            return resp.status, raw.decode("utf-8")
    except urllib.error.HTTPError as e:
        raw_err = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw_err)
        except Exception:
            return e.code, raw_err

def test_full_live_api():
    print("Testing Full API Live Endpoints against http://127.0.0.1:8000 ...\n")

    # 1. Homepage
    status, html = make_request("/")
    assert status == 200 and "CRIMINAL NETWORK ANALYSIS SYSTEM" in html
    print("✓ [1/12] GET / (Homepage HTML) -> 200 OK")

    # 2. Health Check
    status, data = make_request("/api/health")
    assert status == 200 and data["status"] == "healthy"
    print(f"✓ [2/12] GET /api/health -> 200 OK (Nodes: {data['total_nodes']}, Edges: {data['total_edges']})")

    # 3. Login
    status, auth_data = make_request("/api/auth/login", method="POST", body={
        "username": "io_rajesh",
        "password": "iopassword"
    })
    assert status == 200 and "access_token" in auth_data
    token = auth_data["access_token"]
    print("✓ [3/12] POST /api/auth/login -> 200 OK (JWT Issued)")

    # 4. Current User Profile
    status, user_data = make_request("/api/auth/me", token=token)
    assert status == 200 and user_data["user"]["username"] == "io_rajesh"
    print(f"✓ [4/12] GET /api/auth/me -> 200 OK (User: {user_data['user']['full_name']})")

    # 5. Full Graph
    status, graph_data = make_request("/api/graph", token=token)
    assert status == 200 and len(graph_data["nodes"]) > 0
    print(f"✓ [5/12] GET /api/graph -> 200 OK ({len(graph_data['nodes'])} Nodes, {len(graph_data['edges'])} Edges)")

    # 6. Real-time NLP Preview
    status, nlp_data = make_request("/api/cases/preview", method="POST", body={
        "narrative_text": "Accused Sunil Verma @ Bunty driving car DL 01 AB 9988 with phone 9876543210 and account 502000881923."
    }, token=token)
    assert status == 200 and len(nlp_data["extracted_entities"]["phones"]) == 1
    print("✓ [6/12] POST /api/cases/preview -> 200 OK (NLP Entity Recognition Verified)")

    # 7. Key Players Ranking
    status, players_data = make_request("/api/analytics/key-players", token=token)
    assert status == 200 and len(players_data["rankings"]) > 0
    top_suspect = players_data["rankings"][0]
    print(f"✓ [7/12] GET /api/analytics/key-players -> 200 OK (Top Suspect: {top_suspect['name']}, Risk: {top_suspect['risk_score']})")

    # 8. Louvain Communities
    status, comm_data = make_request("/api/analytics/communities", token=token)
    assert status == 200 and comm_data["total_communities"] >= 1
    print(f"✓ [8/12] GET /api/analytics/communities -> 200 OK ({comm_data['total_communities']} Crime Cells, Modularity: {comm_data['modularity_score']})")

    # 9. Shortest Path Finder
    status, path_data = make_request("/api/analytics/shortest-path?source_id=P_FARHAN_01&target_id=P_ROHAN_03", token=token)
    assert status == 200 and path_data["found"] is True
    print(f"✓ [9/12] GET /api/analytics/shortest-path -> 200 OK (Hop Distance: {path_data['hop_distance']})")

    # 10. Link Prediction
    status, link_data = make_request("/api/analytics/link-predictions?top_k=5", token=token)
    assert status == 200 and len(link_data["predictions"]) > 0
    print(f"✓ [10/12] GET /api/analytics/link-predictions -> 200 OK ({len(link_data['predictions'])} Predictions Generated)")

    # 11. Cross-Jurisdiction OCND Links
    status, jur_data = make_request("/api/jurisdictions/cross-links", token=token)
    assert status == 200 and len(jur_data["alerts"]) > 0
    print(f"✓ [11/12] GET /api/jurisdictions/cross-links -> 200 OK ({len(jur_data['alerts'])} Multi-State Syndicates Detected)")

    # 12. Cryptographic Audit Chain Verification
    status, audit_data = make_request("/api/audit/verify-chain", token=token)
    assert status == 200 and audit_data["valid"] is True
    print(f"✓ [12/12] GET /api/audit/verify-chain -> 200 OK ({audit_data['message']})")

    print("\n" + "=" * 60)
    print("ALL 12 API INTEGRATION TESTS PASSED 100% SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    test_full_live_api()
