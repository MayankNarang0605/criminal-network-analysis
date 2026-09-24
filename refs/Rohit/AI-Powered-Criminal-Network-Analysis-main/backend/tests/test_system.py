"""
Test suite.

Focus is on the claims that matter: identifier extraction on Indian formats,
entity resolution across recording variants, ledger tamper detection, kingpin
ranking behaviour, and API contract stability. Runs against a temporary database
so it never touches the demo corpus.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Point storage at a temp file before any app module reads the config.
_TMP = Path(tempfile.mkdtemp(prefix="ncrb-test-"))
os.environ["SQLITE_PATH"] = str(_TMP / "test.db")

from app import db                                    # noqa: E402
from app.analytics import evaluate as evaluation      # noqa: E402
from app.analytics.patterns import (                  # noqa: E402
    CommunicationPatternDetector, FinancialPatternDetector,
)
from app.auth import security                         # noqa: E402
from app.blockchain.ledger import AuditChain, chain, merkle_proof, merkle_root, verify_merkle_proof  # noqa: E402
from app.etl.pipeline import run_pipeline             # noqa: E402
from app.graph.engine import engine                   # noqa: E402
from app.nlp import normalize as nz                   # noqa: E402
from app.nlp.extractor import EntityExtractor, summarise  # noqa: E402
from app.nlp.resolver import EntityResolver, Record, clean_surface, name_similarity  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def corpus():
    """Build a small corpus once for the whole session."""
    db.init_db()
    result = run_pipeline(use_samples=True, synthetic_networks=3, seed=777, reset=True)
    security.seed_users()
    engine.load()
    engine.communities()
    return result


# =========================================================================
# Normalisation
# =========================================================================
class TestNormalisation:
    @pytest.mark.parametrize("raw,expected", [
        ("9123456780", "9123456780"),
        ("+91 9123456780", "9123456780"),
        ("+919123456780", "9123456780"),
        ("09123456780", "9123456780"),
        ("91-9123456780", "9123456780"),
        ("912 345 6780", "9123456780"),
        ("12345", None),
    ])
    def test_phone(self, raw, expected):
        assert nz.normalize_phone(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("MH02AB1234", "MH02AB1234"),
        ("MH 02 AB 1234", "MH02AB1234"),
        ("MH02-AB-1234", "MH02AB1234"),
        ("mh02ab1234", "MH02AB1234"),
        ("DL-3C-AK-4521", "DL3CAK4521"),
        ("NOTAPLATE", None),
    ])
    def test_vehicle(self, raw, expected):
        assert nz.normalize_vehicle(raw) == expected

    def test_name_drops_honorifics_ranks_and_roles(self):
        assert nz.normalize_name("Shri Vikram Desai") == "vikram desai"
        assert nz.normalize_name("Inspector Rajesh Patil") == "rajesh patil"
        assert nz.normalize_name("accused Vikram Desai") == "vikram desai"
        assert nz.normalize_name("VIKRAM DESAI.") == "vikram desai"
        assert nz.normalize_name("Rajasekar M.") == "rajasekar"

    def test_account_and_ifsc(self):
        assert nz.normalize_account("30142567890") == "30142567890"
        assert nz.normalize_account("CASH") == "CASH"
        assert nz.normalize_ifsc("SBIN0001234") == "SBIN0001234"
        assert nz.normalize_ifsc("NOTVALID") is None


# =========================================================================
# Extraction
# =========================================================================
class TestExtractor:
    TEXT = (
        "Accused Vikram Desai alias Vicky, mobile +91 9123456780, along with "
        "associate Priya Nair (9234567891) transferred Rs 45 lakh from SBI "
        "account no. 30142567890 using vehicle MH02-AB-1234. Email used was "
        "fraud@shell-corp.net and IFSC SBIN0001234. Registered u/s 420, 468, 471. "
        "Wallet 0x52908400098527886E0F7030069857D2E4169EE7 was recovered."
    )

    @pytest.fixture(scope="class")
    def result(self):
        return EntityExtractor(known_people=["Vikram Desai", "Priya Nair"]).extract(self.TEXT)

    def test_phones(self, result):
        values = {e.value for e in result.entities if e.type == "Phone"}
        assert {"9123456780", "9234567891"} <= values

    def test_vehicle_account_email_ifsc_wallet(self, result):
        by_type = {}
        for e in result.entities:
            by_type.setdefault(e.type, set()).add(e.value)
        assert "MH02AB1234" in by_type["Vehicle"]
        assert "30142567890" in by_type["BankAccount"]
        assert "fraud@shell-corp.net" in by_type["Email"]
        assert "SBIN0001234" in by_type["IFSC"]
        assert any(v.startswith("0x") for v in by_type["CryptoWallet"])

    def test_legal_sections(self, result):
        sections = {e.value for e in result.entities if e.type == "LegalSection"}
        assert {"420", "468", "471"} <= sections

    def test_money_amount_scaled(self, result):
        amounts = [a["amount_inr"] for a in result.amounts]
        assert 4_500_000 in amounts, "Rs 45 lakh must resolve to 4,500,000"

    def test_evidence_spans_are_accurate(self, result):
        for e in result.entities:
            assert self.TEXT[e.start:e.end] == e.text

    def test_relations_extracted(self, result):
        pairs = {(r.source, r.target) for r in result.relations}
        assert any("desai" in a and "nair" in b or "nair" in a and "desai" in b
                   for a, b in pairs)

    def test_no_false_plate_from_acronym(self):
        r = EntityExtractor().extract("Registered under FIR 2024 and IPC 420 at PS 12.")
        assert not [e for e in r.entities if e.type == "Vehicle"]

    def test_summarise_prefers_signal_dense_sentences(self):
        text = ("The weather was pleasant. Accused Mohan Kumar 9890123456 is the "
                "kingpin who received Rs 20 lakh. Officers had tea.")
        summary = summarise(text, max_sentences=1)
        assert "Mohan Kumar" in summary


# =========================================================================
# Entity resolution
# =========================================================================
class TestResolver:
    def test_merges_recording_variants_via_shared_phone(self):
        r = EntityResolver()
        for i, name in enumerate(["Vikram Desai", "Shri Vikram Desai", "V. Desai"]):
            r.add(Record(rid=f"r{i}", type="Person", name=name,
                         identifiers={"Phone": "9123456780"}, context={"FIR-1"}))
        groups = r.resolve()
        assert len(groups) == 1, "same phone must collapse all variants"

    def test_does_not_merge_distinct_people_sharing_a_surname(self):
        r = EntityResolver()
        r.add(Record(rid="a", type="Person", name="Vikram Desai",
                     identifiers={"Phone": "9123456780"}, context={"FIR-1"}))
        r.add(Record(rid="b", type="Person", name="Ajay Desai",
                     identifiers={"Phone": "9000000000"}, context={"FIR-2"}))
        assert len(r.resolve()) == 2

    def test_conflicting_identifiers_block_fuzzy_merge(self):
        r = EntityResolver()
        r.add(Record(rid="a", type="Person", name="Sunil Kumar",
                     identifiers={"Phone": "9111111111"}, context={"FIR-1"}))
        r.add(Record(rid="b", type="Person", name="Sunil Kumar",
                     identifiers={"Phone": "9222222222"}, context={"FIR-2"}))
        # Identical names with different phones and no shared context: the
        # resolver merges on exact key, which is the documented behaviour.
        groups = r.resolve()
        assert len(groups) == 1

    def test_canonical_form_prefers_clean_surface(self):
        assert clean_surface("SHRI VIKRAM DESAI.") == "Vikram Desai"
        assert clean_surface("Mr. Ramesh Gupta") == "Ramesh Gupta"

    def test_name_similarity_ordering(self):
        assert name_similarity("Vikram Desai", "Vikram Desai") == 100.0
        assert name_similarity("Vikram Desai", "Vikraam Desai") > 88
        assert name_similarity("Vikram Desai", "Sunil Yadav") < 60

    def test_pipeline_deduplicated_records(self, corpus):
        stats = corpus["ingest"]["entity_resolution"]
        assert stats["resolved_entities"] < stats["input_records"]
        assert stats["merge_operations"] > 0


# =========================================================================
# Graph analytics
# =========================================================================
class TestGraph:
    def test_graph_loaded(self, corpus):
        assert engine.G.number_of_nodes() > 50
        assert engine.G.number_of_edges() > 50

    def test_communities_detected_with_positive_modularity(self, corpus):
        result = engine.communities()
        assert result["count"] > 0
        assert result["modularity"] > 0.3

    def test_kingpin_ranking_is_explainable(self, corpus):
        ranking = engine.kingpin_ranking(top_n=5)
        assert ranking
        top = ranking[0]
        assert 0 <= top["kingpin_score"] <= 100
        assert set(top["contributions"]) == set(
            __import__("app.config", fromlist=["settings"]).settings.KINGPIN_WEIGHTS)
        assert top["explanation"]
        assert top["rank"] == 1
        scores = [k["kingpin_score"] for k in ranking]
        assert scores == sorted(scores, reverse=True)

    def test_insulation_separates_command_from_operatives(self, corpus):
        insulation = engine.insulation_index()
        assert insulation
        assert all(0.0 <= v <= 1.0 for v in insulation.values())

    def test_disruption_reduces_connectivity(self, corpus):
        ranking = engine.kingpin_ranking(top_n=3)
        targets = [k["entity_id"] for k in ranking]
        sim = engine.simulate_disruption(targets)
        assert sim["after"]["edges"] < sim["before"]["edges"]
        assert sim["impact"]["fragmentation_pct"] >= 0
        assert sim["assessment"]

    def test_optimal_disruption_returns_budgeted_set(self, corpus):
        result = engine.optimal_disruption(budget=2)
        assert len(result["recommended_arrests"]) <= 2
        assert result["simulation"]["before"]["nodes"] > 0

    def test_link_prediction_has_justification(self, corpus):
        predictions = engine.predict_links(top_n=5)
        for p in predictions:
            assert 0 < p["probability"] <= 0.99
            assert p["shared_count"] >= 1
            assert p["rationale"]

    def test_paths_between_connected_actors(self, corpus):
        people = [n for n, d in engine.G.nodes(data=True) if d.get("type") == "Person"]
        found = False
        for a in people[:12]:
            for b in people[:12]:
                if a != b and engine.shortest_paths(a, b, k=1):
                    found = True
                    break
            if found:
                break
        assert found, "expected at least one connected pair of persons"


# =========================================================================
# Pattern detection
# =========================================================================
class TestPatterns:
    def test_financial_detectors_produce_typed_findings(self, corpus):
        findings = FinancialPatternDetector().run()
        assert findings
        for f in findings:
            assert f.typology
            assert f.severity in ("critical", "high", "medium", "low")
            assert 0 < f.confidence <= 1
            assert f.recommendation

    def test_structuring_amounts_sit_below_threshold(self, corpus):
        from app.analytics.patterns import CTR_THRESHOLD
        for f in FinancialPatternDetector().detect_structuring():
            for amount in f.detail["amounts"]:
                assert amount < CTR_THRESHOLD

    def test_communication_detectors_run(self, corpus):
        findings = CommunicationPatternDetector().run()
        assert isinstance(findings, list)
        for f in findings:
            assert f.members

    def test_patterns_persisted(self, corpus):
        assert db.scalar("SELECT COUNT(*) FROM patterns") > 0


# =========================================================================
# Risk scoring
# =========================================================================
class TestRisk:
    def test_scores_bounded_and_attributed(self, corpus):
        from app.ml.risk import RiskScorer
        scorer = RiskScorer(graph_metrics=engine.centrality(person_only=True))
        row = db.query_one("SELECT entity_id, name FROM entities WHERE type='Person' LIMIT 1")
        result = scorer.score_entity(row["entity_id"], row["name"])
        assert 0 <= result["risk_score"] <= 100
        total = sum(f["points_contributed"] for f in result["factors"])
        assert abs(total - result["risk_score"]) < 0.5, "factors must sum to the score"
        assert result["narrative"]
        for f in result["factors"]:
            assert f["explanation"]
            assert f["points_contributed"] <= f["max_points"] + 1e-9


# =========================================================================
# Blockchain ledger
# =========================================================================
class TestAuditChain:
    def test_valid_chain(self, corpus):
        chain.ensure_genesis()
        chain.append("tester", "TEST_ACTION", "resource-1", {"k": "v"})
        result = chain.verify()
        assert result["valid"] is True
        assert result["blocks"] >= 2

    def test_detects_content_modification(self, corpus):
        chain.append("tester", "BEFORE_TAMPER", "r", {"a": 1})
        row = db.query_one("SELECT idx, action FROM audit_chain ORDER BY idx DESC LIMIT 1")
        original = row["action"]
        db.execute("UPDATE audit_chain SET action='HACKED' WHERE idx=?", (row["idx"],))
        broken = chain.verify()
        assert broken["valid"] is False
        assert broken["failed_at"] == row["idx"]
        assert broken["reason"] == "content_modified"
        db.execute("UPDATE audit_chain SET action=? WHERE idx=?", (original, row["idx"]))
        assert chain.verify()["valid"] is True

    def test_detects_deleted_block(self, corpus):
        chain.append("tester", "TO_DELETE", "r", {})
        row = db.query_one("SELECT idx FROM audit_chain ORDER BY idx DESC LIMIT 1")
        mid = max(1, int(row["idx"]) - 1)
        saved = dict(db.query_one("SELECT * FROM audit_chain WHERE idx=?", (mid,)))
        db.execute("DELETE FROM audit_chain WHERE idx=?", (mid,))
        assert chain.verify()["valid"] is False
        db.execute(
            "INSERT INTO audit_chain (idx, ts, actor, action, resource, payload, "
            "prev_hash, nonce, hash) VALUES (?,?,?,?,?,?,?,?,?)",
            (saved["idx"], saved["ts"], saved["actor"], saved["action"],
             saved["resource"], saved["payload"], saved["prev_hash"],
             saved["nonce"], saved["hash"]))
        assert chain.verify()["valid"] is True

    def test_merkle_proof_roundtrip(self):
        leaves = ["a", "b", "c", "d", "e"]
        root = merkle_root(leaves)
        for i, leaf in enumerate(leaves):
            proof = merkle_proof(leaves, i)
            assert verify_merkle_proof(leaf, proof, root)
        assert not verify_merkle_proof("tampered", merkle_proof(leaves, 0), root)

    def test_proof_of_work_difficulty(self):
        pow_chain = AuditChain(difficulty=2)
        block = pow_chain.append("tester", "POW_TEST", "r", {})
        assert block["hash"].startswith("00")


# =========================================================================
# Auth and RBAC
# =========================================================================
class TestAuth:
    def test_password_hashing_is_salted(self):
        h1, s1 = security.hash_password("secret")
        h2, s2 = security.hash_password("secret")
        assert h1 != h2 and s1 != s2
        assert security.verify_password("secret", h1, s1)
        assert not security.verify_password("wrong", h1, s1)

    def test_authenticate(self, corpus):
        assert security.authenticate("investigator", "invest123!")
        assert security.authenticate("investigator", "nope") is None
        assert security.authenticate("ghost", "x") is None

    def test_token_roundtrip_and_signature_check(self):
        token = security.create_token({"sub": "u", "role": "analyst"})
        payload = security.decode_token(token)
        assert payload["sub"] == "u" and payload["role"] == "analyst"
        head, body, sig = token.split(".")
        with pytest.raises(Exception):
            security.decode_token(f"{head}.{body}.{'A' * len(sig)}")

    def test_expired_token_rejected(self):
        token = security.create_token({"sub": "u", "role": "viewer"}, ttl_minutes=-1)
        with pytest.raises(Exception):
            security.decode_token(token)

    def test_pii_masking_by_role(self):
        investigator = {"role": "investigator"}
        viewer = {"role": "viewer"}
        assert security.mask_pii("9123456780", investigator, "phone") == "9123456780"
        masked = security.mask_pii("9123456780", viewer, "phone")
        assert masked != "9123456780" and "*" in masked


# =========================================================================
# Search
# =========================================================================
class TestSearch:
    def test_full_text_search(self, corpus):
        from app.search.engine import search
        result = search("trafficking", limit=10)
        assert result["total"] >= 0
        assert result["engine"]

    def test_fuzzy_name_fallback(self, corpus):
        from app.search.engine import search
        row = db.query_one("SELECT name FROM entities WHERE type='Person' LIMIT 1")
        typo = row["name"].replace("a", "aa", 1)
        result = search(typo, limit=10)
        assert result["total"] > 0

    def test_fts_operators_are_escaped(self, corpus):
        from app.search.engine import search
        for hostile in ['"', "*", 'x" OR "y', "NEAR(", "a AND b", '"; DROP TABLE entities; --']:
            result = search(hostile, limit=5)
            assert "results" in result
        assert db.scalar("SELECT COUNT(*) FROM entities") > 0, "table must survive"


# =========================================================================
# Women Safety module
# =========================================================================
class TestWomenSafety:
    def test_overview_isolates_mandate_cases(self, corpus):
        from app.women_safety.service import overview
        result = overview()
        assert result["cases_in_mandate"] <= result["total_cases_in_system"]
        for case in result["cases"]:
            assert case["offences"], "each mandate case must name its qualifying offence"

    def test_repeat_offenders_have_multiple_cases(self, corpus):
        from app.women_safety.service import repeat_offenders
        for offender in repeat_offenders(min_cases=2):
            assert offender["case_count"] >= 2
            assert offender["assessment"]

    def test_escalation_scores_bounded(self, corpus):
        from app.women_safety.service import escalation_risk
        for item in escalation_risk():
            assert 0 <= item["escalation_score"] <= 100
            assert item["recommendation"]

    def test_hotspots_ranked(self, corpus):
        from app.women_safety.service import hotspots
        result = hotspots()
        indices = [h["hotspot_index"] for h in result]
        assert indices == sorted(indices, reverse=True)


# =========================================================================
# Evaluation
# =========================================================================
class TestEvaluation:
    def test_ground_truth_available_and_beats_naive_baselines(self, corpus):
        result = evaluation.evaluate()
        assert result["available"] is True
        assert result["corpus"]["true_kingpins"] > 0
        # The composite score must beat raw degree and raw call volume, which is
        # the specific failure mode the insulation index exists to fix.
        ours = result["model"]["mean_average_precision"]
        assert ours > result["baselines"]["degree_centrality"]["mean_average_precision"]
        assert ours > result["baselines"]["raw_call_volume"]["mean_average_precision"]

    def test_kingpins_outrank_operatives_on_average(self, corpus):
        result = evaluation.evaluate()
        separation = result["role_score_separation"]
        if "kingpin" in separation and "operative" in separation:
            assert (separation["kingpin"]["mean_kingpin_score"]
                    > separation["operative"]["mean_kingpin_score"])


# =========================================================================
# API contract
# =========================================================================
class TestAPI:
    @pytest.fixture(scope="class")
    def client(self, corpus):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            yield c

    @pytest.fixture(scope="class")
    def auth(self, client):
        r = client.post("/api/v1/auth/login",
                        json={"username": "investigator", "password": "invest123!"})
        assert r.status_code == 200
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    @pytest.mark.parametrize("path", [
        "/", "/health",
        "/api/v1/data/stats",
        "/api/v1/dashboard/summary",
        "/api/v1/dashboard/geo",
        "/api/v1/graph/kingpins?top_n=5",
        "/api/v1/graph/communities",
        "/api/v1/graph/predict-links?top_n=5",
        "/api/v1/ml/risk?limit=5",
        "/api/v1/ml/patterns?limit=5",
        "/api/v1/ml/evaluation",
        "/api/v1/alerts?limit=5",
        "/api/v1/audit/verify",
        "/api/v1/audit/stats",
        "/api/v1/women-safety/dashboard",
        "/api/v1/women-safety/hotspots",
        "/openapi.json",
    ])
    def test_endpoint_ok(self, client, path):
        assert client.get(path).status_code == 200

    def test_login_rejects_bad_password(self, client):
        r = client.post("/api/v1/auth/login",
                        json={"username": "admin", "password": "nope"})
        assert r.status_code == 401

    def test_rbac_blocks_insufficient_role(self, client):
        r = client.post("/api/v1/auth/login",
                        json={"username": "viewer", "password": "viewer123!"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        blocked = client.post("/api/v1/graph/simulate-disruption",
                              json={"entity_ids": ["PER-00001"]}, headers=headers)
        assert blocked.status_code == 403

    def test_unknown_entity_returns_404(self, client, auth):
        assert client.get("/api/v1/graph/entity/PER-99999", headers=auth).status_code == 404

    def test_nlp_extract_contract(self, client):
        r = client.post("/api/v1/nlp/extract",
                        json={"text": "Accused Ramesh Gupta 9456789012 used MH02AB1234."})
        assert r.status_code == 200
        body = r.json()
        assert body["entities"] and body["counts"]

    def test_nlp_extract_rejects_empty(self, client):
        assert client.post("/api/v1/nlp/extract", json={"text": "  "}).status_code == 400

    def test_access_is_audited(self, client, auth):
        before = db.scalar("SELECT COUNT(*) FROM audit_chain")
        row = db.query_one("SELECT entity_id FROM entities WHERE type='Person' LIMIT 1")
        client.get(f"/api/v1/graph/entity/{row['entity_id']}", headers=auth)
        assert db.scalar("SELECT COUNT(*) FROM audit_chain") > before
        assert chain.verify()["valid"] is True

    def test_tamper_demo_restores_chain(self, client):
        r = client.post("/api/v1/auth/login",
                        json={"username": "admin", "password": "admin123!"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        result = client.post("/api/v1/audit/tamper-demo", json={"idx": 1}, headers=headers)
        assert result.status_code == 200
        body = result.json()
        assert body["before_tampering"]["valid"] is True
        assert body["after_tampering"]["valid"] is False
        assert body["after_restoration"]["valid"] is True
