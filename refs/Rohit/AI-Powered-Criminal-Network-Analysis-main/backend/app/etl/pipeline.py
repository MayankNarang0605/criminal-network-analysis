"""
Ingestion and enrichment pipeline.

Single orchestrated flow:

  load sources -> extract entities (NLP) -> resolve duplicates -> persist
  entities/relationships -> build derived edges from CDR + ledger -> graph
  analytics -> pattern detection -> risk scoring -> alerts -> search index

Runs synchronously and completes in seconds on the demo corpus, which matters:
an investigator uploading a new CDR dump gets refreshed intelligence immediately
rather than waiting on a queue. `Pipeline.run()` is idempotent.
"""
from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app import db
from app.blockchain.ledger import chain, log
from app.config import DATA_DIR
from app.etl.generator import Corpus, generate_corpus
from app.graph.engine import engine
from app.nlp import normalize as nz
from app.nlp import ipc
from app.nlp.extractor import EntityExtractor, summarise
from app.nlp.resolver import EntityResolver, Record

ENTITY_PREFIX = {
    "Person": "PER", "Organization": "ORG", "Phone": "PHN", "Vehicle": "VEH",
    "BankAccount": "ACC", "Location": "LOC", "Event": "EVT", "Email": "EML",
    "CryptoWallet": "WAL", "Bank": "BNK", "LegalSection": "SEC", "IFSC": "IFS",
    "PAN": "PAN", "Aadhaar": "AAD", "IMEI": "IMI", "Date": "DTE",
}
PERSISTED_TYPES = {
    "Person", "Organization", "Phone", "Vehicle", "BankAccount",
    "Location", "Email", "CryptoWallet",
}


@dataclass
class IngestStats:
    sources: dict[str, int] = field(default_factory=dict)
    entities_created: dict[str, int] = field(default_factory=dict)
    relationships_created: dict[str, int] = field(default_factory=dict)
    resolution: dict[str, Any] = field(default_factory=dict)
    extraction: dict[str, int] = field(default_factory=dict)
    timings_ms: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sources": self.sources,
            "entities_created": self.entities_created,
            "entities_total": sum(self.entities_created.values()),
            "relationships_created": self.relationships_created,
            "relationships_total": sum(self.relationships_created.values()),
            "entity_resolution": self.resolution,
            "nlp_extraction": self.extraction,
            "timings_ms": self.timings_ms,
        }


class Pipeline:
    def __init__(self) -> None:
        self.stats = IngestStats()
        self._entity_ids: dict[tuple[str, str], str] = {}   # (type, normalized) -> entity_id
        self._counters: dict[str, int] = defaultdict(int)
        self._entities: dict[str, dict] = {}
        self._relationships: dict[tuple[str, str, str], dict] = {}
        self._case_links: set[tuple[str, str, str]] = set()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self, use_samples: bool = True, synthetic_networks: int = 6,
            seed: int = 20260828, reset: bool = True) -> dict:
        t0 = datetime.now(timezone.utc)
        db.init_db()
        if reset:
            db.reset_db()

        firs, cdr, txns, ground_truth = self._collect_sources(
            use_samples=use_samples, synthetic_networks=synthetic_networks, seed=seed)

        self._persist_cases(firs)
        self._persist_cdr(cdr)
        self._persist_transactions(txns)
        self._persist_ground_truth(ground_truth)
        self._mark("load")

        resolver = self._extract_and_resolve(firs)
        self._mark("nlp_and_resolution")

        self._build_cdr_edges()
        self._build_transaction_edges()
        self._build_shared_attribute_edges()
        self._mark("derived_edges")

        self._flush()
        self._mark("persist")

        analytics = self.enrich()
        self._mark("analytics")

        self._build_search_index()
        self._mark("search_index")

        chain.ensure_genesis()
        log("system", "PIPELINE_RUN", "corpus",
            firs=len(firs), cdr=len(cdr), transactions=len(txns),
            entities=sum(self.stats.entities_created.values()))

        total_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
        self.stats.timings_ms["total"] = total_ms
        return {
            "status": "completed",
            "ingest": self.stats.to_dict(),
            "analytics": analytics,
            "resolution_sample": resolver.merges[:15],
        }

    def _mark(self, stage: str) -> None:
        now = datetime.now(timezone.utc)
        prev = getattr(self, "_last_mark", None) or getattr(self, "_t0", now)
        self.stats.timings_ms[stage] = int((now - prev).total_seconds() * 1000)
        self._last_mark = now

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------
    def _collect_sources(self, use_samples: bool, synthetic_networks: int,
                         seed: int) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
        firs: list[dict] = []
        cdr: list[dict] = []
        txns: list[dict] = []
        ground_truth: list[dict] = []

        if use_samples:
            firs += self._load_sample_firs()
            cdr += self._load_sample_cdr()
            txns += self._load_sample_transactions()
            self.stats.sources["sample_firs"] = len(firs)
            self.stats.sources["sample_cdr"] = len(cdr)
            self.stats.sources["sample_transactions"] = len(txns)

        if synthetic_networks > 0:
            corpus: Corpus = generate_corpus(networks=synthetic_networks, seed=seed)
            firs += corpus.firs
            cdr += corpus.cdr
            txns += corpus.transactions
            ground_truth += corpus.ground_truth
            self.stats.sources["generated_firs"] = len(corpus.firs)
            self.stats.sources["generated_cdr"] = len(corpus.cdr)
            self.stats.sources["generated_transactions"] = len(corpus.transactions)
            self.stats.sources["generated_networks"] = synthetic_networks

        return firs, cdr, txns, ground_truth

    def _load_sample_firs(self) -> list[dict]:
        path = DATA_DIR / "sample_firs.json"
        if not path.exists():
            return []
        records = json.loads(path.read_text(encoding="utf-8"))
        for r in records:
            r.setdefault("crime_type", self._infer_crime_type(r.get("ipc_sections", [])))
        return records

    def _load_sample_cdr(self) -> list[dict]:
        path = DATA_DIR / "sample_cdr.csv"
        if not path.exists():
            return []
        out: list[dict] = []
        with path.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                caller = nz.normalize_phone(row.get("caller_number", ""))
                callee = nz.normalize_phone(row.get("callee_number", ""))
                if not caller or not callee:
                    continue
                out.append({
                    "call_id": row.get("call_id"),
                    "caller": caller,
                    "callee": callee,
                    "ts": f"{row.get('call_date')} {row.get('call_time')}",
                    "duration": int(row.get("duration_seconds") or 0),
                    "call_type": row.get("call_type"),
                    "tower_id": row.get("tower_id"),
                    "tower_name": row.get("tower_location"),
                    "lat": _float(row.get("tower_lat")),
                    "lon": _float(row.get("tower_lon")),
                })
        return out

    def _load_sample_transactions(self) -> list[dict]:
        path = DATA_DIR / "sample_transactions.csv"
        if not path.exists():
            return []
        out: list[dict] = []
        with path.open("r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                out.append({
                    "txn_id": row.get("txn_id"),
                    "ts": f"{row.get('date')} {row.get('time')}",
                    "from_account": nz.normalize_account(row.get("from_account", "")) or "CASH",
                    "from_bank": row.get("from_bank"),
                    "from_name": row.get("from_name"),
                    "to_account": nz.normalize_account(row.get("to_account", "")) or "CASH",
                    "to_bank": row.get("to_bank"),
                    "to_name": row.get("to_name"),
                    "amount": _float(row.get("amount_inr")) or 0.0,
                    "txn_type": row.get("txn_type"),
                    "description": row.get("description"),
                    "flagged": 1 if str(row.get("suspicious_flag", "")).lower() == "true" else 0,
                })
        return out

    @staticmethod
    def _infer_crime_type(sections: list[str]) -> str:
        domains = ipc.domains_of(sections)
        return domains[0] if domains else "Unclassified"

    # ------------------------------------------------------------------
    # Persist raw records
    # ------------------------------------------------------------------
    def _persist_cases(self, firs: list[dict]) -> None:
        rows = []
        for r in firs:
            sections = r.get("ipc_sections", []) or []
            rows.append((
                r["fir_id"],
                r.get("title") or f"{self._infer_crime_type(sections)} — {r.get('station', '')}",
                r.get("description", ""),
                r.get("station"), r.get("district"), r.get("state"),
                db.jdump(sections),
                r.get("crime_type") or self._infer_crime_type(sections),
                r.get("status"), r.get("priority"), str(r.get("date_filed") or "")[:10],
                r.get("investigating_officer"), db.jdump(r),
            ))
        db.executemany(
            "INSERT OR REPLACE INTO cases (fir_id, title, description, station, district, "
            "state, ipc_sections, crime_type, status, priority, date_filed, officer, raw) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)

    def _persist_cdr(self, cdr: list[dict]) -> None:
        db.executemany(
            "INSERT INTO cdr (call_id, caller, callee, ts, duration, call_type, "
            "tower_id, tower_name, lat, lon) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(c.get("call_id"), c["caller"], c["callee"], c["ts"], c.get("duration", 0),
              c.get("call_type"), c.get("tower_id"), c.get("tower_name"),
              c.get("lat"), c.get("lon")) for c in cdr])

    def _persist_transactions(self, txns: list[dict]) -> None:
        db.executemany(
            "INSERT INTO transactions (txn_id, ts, from_account, from_bank, from_name, "
            "to_account, to_bank, to_name, amount, txn_type, description, flagged) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(t.get("txn_id"), t["ts"], t["from_account"], t.get("from_bank"),
              t.get("from_name"), t["to_account"], t.get("to_bank"), t.get("to_name"),
              t["amount"], t.get("txn_type"), t.get("description"),
              int(t.get("flagged", 0))) for t in txns])

    def _persist_ground_truth(self, gt: list[dict]) -> None:
        if not gt:
            return
        db.executemany(
            "INSERT OR REPLACE INTO ground_truth (entity_name, phone, true_role, network) "
            "VALUES (?,?,?,?)",
            [(g["entity_name"], g.get("phone"), g["true_role"], g["network"]) for g in gt])

    # ------------------------------------------------------------------
    # Incremental helpers (used by Live Investigation — dashboard path)
    # ------------------------------------------------------------------
    def _load_existing_state(self) -> None:
        """Hydrate counters and lookup so new IDs don't collide with DB."""
        self._entity_ids.clear()
        self._counters.clear()
        self._entities.clear()
        self._relationships.clear()
        self._case_links.clear()
        for row in db.query("SELECT entity_id, type, normalized FROM entities"):
            self._entity_ids[(row["type"], row["normalized"])] = row["entity_id"]
            try:
                num = int(row["entity_id"].split("-")[1])
                self._counters[row["type"]] = max(self._counters.get(row["type"], 0), num)
            except Exception:
                pass

    def add_case(self, fir: dict, recompute: bool = True) -> dict:
        """Add a single FIR (from dashboard) without wiping existing data."""
        db.init_db()
        self._load_existing_state()
        # Basic validation — mirror sample_firs.json shape
        if not fir.get("fir_id"):
            import uuid as _uuid
            fir["fir_id"] = f"FIR-{fir.get('state','XX')[:2].upper()}-{str(_uuid.uuid4())[:8].upper()}"
        fir.setdefault("crime_type", self._infer_crime_type(fir.get("ipc_sections", [])))
        fir.setdefault("status", "Under Investigation")
        fir.setdefault("priority", "Medium")
        fir.setdefault("accused", [])
        fir.setdefault("description", fir.get("title",""))
        fir.setdefault("ipc_sections", fir.get("ipc_sections", []))
        # Persist case row
        self._persist_cases([fir])
        # Extract + resolve just this FIR against existing corpus
        resolver = self._extract_single_fir(fir)
        self._flush()
        chain.ensure_genesis()
        log("investigator", "CASE_CREATED", fir["fir_id"], accused=len(fir.get("accused",[])))
        analytics = self.enrich() if recompute else {}
        self._build_search_index()
        # Return what dashboard needs to navigate
        created = []
        for a in fir.get("accused", []):
            eid = self._lookup_entity("Person", a.get("name",""))
            if eid:
                row = db.query_one("SELECT name, risk_score, kingpin_score FROM entities WHERE entity_id=?", (eid,))
                created.append({"entity_id": eid, "name": row["name"] if row else a.get("name"), "input": a})
        return {"fir_id": fir["fir_id"], "created_entities": created, "ingest": self.stats.to_dict(), "analytics": analytics, "resolution": resolver.stats() if resolver else {}}

    def update_case(self, fir_id: str, fir: dict, editor: str = "admin", recompute: bool = True) -> dict:
        """Update a registered FIR — admin only, versioned. Supports any field including fir_id rename."""
        db.init_db()
        self._load_existing_state()
        old = db.query_one("SELECT * FROM cases WHERE fir_id=?", (fir_id,))
        if old is None:
            raise ValueError(f"Case {fir_id} not found")
        # Snapshot old version
        old_version = (old["version"] or 1) if "version" in old.keys() else 1
        try:
            db.execute(
                "INSERT INTO cases_versions (fir_id, version, snapshot, edited_by) VALUES (?,?,?,?)",
                (fir_id, old_version, db.jdump(dict(old)), editor),
            )
        except Exception:
            pass
        # Merge old raw with new fields (2.all — allow any key including fir_id)
        old_raw = db.jload(old["raw"], {})
        # Preserve original fir_id if not provided
        new_fir = dict(old_raw) if isinstance(old_raw, dict) else {}
        # Overlay with new fir payload
        for k, v in fir.items():
            new_fir[k] = v
        new_fir_id = new_fir.get("fir_id", fir_id)
        # Handle fir_id rename collision already checked in API, but ensure new_fir has correct id
        new_fir["fir_id"] = new_fir_id
        new_fir.setdefault("crime_type", self._infer_crime_type(new_fir.get("ipc_sections", [])))
        new_fir.setdefault("status", old["status"] or "Under Investigation")
        new_fir.setdefault("priority", old["priority"] or "Medium")
        new_fir.setdefault("accused", new_fir.get("accused", []))
        new_fir.setdefault("description", new_fir.get("description", old["description"] or old["title"] or ""))
        new_fir.setdefault("ipc_sections", new_fir.get("ipc_sections", []))
        # Cleanup stale links for old fir_id before re-ingest
        # Remove entity_cases for old id
        db.execute("DELETE FROM entity_cases WHERE fir_id=?", (fir_id,))
        # Remove relationships whose evidence was sourced from this FIR (best-effort LIKE on JSON)
        try:
            db.execute("DELETE FROM relationships WHERE evidence LIKE ?", (f'%"source": "FIR:{fir_id}"%',))
            db.execute("DELETE FROM relationships WHERE evidence LIKE ?", (f'%"source":"FIR:{fir_id}"%',))
        except Exception:
            pass
        # If renaming, also cleanup new id just in case (should be empty)
        if new_fir_id != fir_id:
            db.execute("DELETE FROM entity_cases WHERE fir_id=?", (new_fir_id,))
        # Persist updated case row
        if new_fir_id != fir_id:
            # Rename: delete old, insert new via _persist_cases (INSERT OR REPLACE handles new)
            db.execute("DELETE FROM cases WHERE fir_id=?", (fir_id,))
            # Also move any other cases_versions for old id? Keep as history under old id, add note
        # Build row for cases table
        sections = new_fir.get("ipc_sections", []) or []
        # Use direct UPDATE via _persist_cases + version bump
        # First ensure _persist_cases will upsert
        self._persist_cases([new_fir])
        # Bump version/updated_at
        try:
            db.execute("UPDATE cases SET version=?, updated_at=? WHERE fir_id=?", (old_version + 1, datetime.now(timezone.utc).isoformat(), new_fir_id))
        except Exception:
            pass
        # If renamed, ensure old cases_versions entry reflects rename
        if new_fir_id != fir_id:
            try:
                db.execute("UPDATE cases_versions SET fir_id=? WHERE fir_id=?", (new_fir_id, fir_id))
            except Exception:
                pass
            # Also migrate any remaining relationships evidence FIR refs already deleted above
        # Re-extract and rebuild graph for updated FIR
        resolver = self._extract_single_fir(new_fir)
        self._flush()
        chain.ensure_genesis()
        log(editor, "CASE_UPDATED", new_fir_id, from_fir=fir_id, version=old_version + 1)
        analytics = self.enrich() if recompute else {}
        self._build_search_index()
        created = []
        for a in new_fir.get("accused", []):
            eid = self._lookup_entity("Person", a.get("name", ""))
            if eid:
                row = db.query_one("SELECT name FROM entities WHERE entity_id=?", (eid,))
                created.append({"entity_id": eid, "name": row["name"] if row else a.get("name"), "input": a})
        return {"fir_id": new_fir_id, "previous_fir_id": fir_id, "updated_entities": created, "ingest": self.stats.to_dict(), "analytics": analytics, "resolution": resolver.stats() if resolver else {}, "version": old_version + 1}

    def _extract_single_fir(self, fir: dict) -> EntityResolver | None:
        # Seed gazetteer from DB + this fir's structured fields
        people = {r["name"] for r in db.query("SELECT name FROM entities WHERE type='Person'")}
        locs = {r["name"] for r in db.query("SELECT name FROM entities WHERE type='Location'")}
        for a in fir.get("accused", []) or []:
            if a.get("name"): people.add(a["name"])
            if a.get("alias"): people.add(a["alias"])
        comp = fir.get("complainant") or {}
        if comp.get("name"): people.add(comp["name"])
        for loc in fir.get("locations_mentioned", []) or []: locs.add(loc)
        if fir.get("district"): locs.add(fir["district"])
        if fir.get("state"): locs.add(fir["state"])
        extractor = EntityExtractor(known_people=people, known_locations=locs)
        resolver = EntityResolver()
        # Pre-seed resolver with existing persons so hard-identifier merge works across DB
        for row in db.query("SELECT entity_id, name, normalized FROM entities WHERE type='Person'"):
            # Attach known phone if any
            phones = [r["target_id"] for r in db.query("SELECT target_id FROM relationships WHERE source_id=? AND rel_type='USES_PHONE'", (row["entity_id"],))]
            # We store phone normalized as entity name, need lookup
            phone_vals = {}
            for pid in phones:
                prow = db.query_one("SELECT name FROM entities WHERE entity_id=?", (pid,))
                if prow: phone_vals["Phone"] = prow["name"]
            resolver.add(Record(rid=f"db:{row['entity_id']}", type="Person", name=row["name"], identifiers=phone_vals, context=set(), attributes={"db_entity_id": row["entity_id"]}, source="db"))

        fir_id = fir["fir_id"]
        text = fir.get("description","") or ""
        result = extractor.extract(text)
        for ex in result.entities:
            if ex.type == "Person" and ex.extractor.startswith("morph"):
                resolver.add(Record(rid=f"{fir_id}:mention:{ex.start}", type="Person", name=ex.text, context={fir_id}, source=f"FIR:{fir_id}", attributes={"extraction": ex.extractor}))
        for accused in fir.get("accused", []) or []:
            self._add_person_record(resolver, accused, fir_id, role="accused", source=f"FIR:{fir_id}")
        if comp.get("name"):
            self._add_person_record(resolver, comp, fir_id, role="complainant", source=f"FIR:{fir_id}")
        self._register_fir_entities(fir, result, extractor)
        resolver.resolve()
        # Materialise only new/merged clusters that touch this FIR
        for cluster in resolver.canonical_entities():
            if cluster["type"] not in ("Person","Organization"): continue
            # Skip clusters that are pure DB entities with no new fir context
            if fir_id not in cluster["context"] and not any(fir_id in s for s in cluster["sources"]):
                # For DB-seeded records, context is empty; instead check if any member rid starts with fir_id
                member_touch = any(fir_id in m for m in cluster.get("member_names",[]))
                # Fallback: if cluster has a phone that matches new accused phone, it touches
                has_new_phone = any(v in [a.get("phone") and nz.normalize_phone(a.get("phone")) for a in fir.get("accused",[])] for vals in cluster["identifiers"].values() for v in vals)
                if not member_touch and not has_new_phone and cluster["member_count"] > 1:
                    # Keep if resolver merged a new accused into existing DB person via phone — we need to update aliases
                    pass
                elif fir_id not in cluster["context"]:
                    continue
            eid = self._ensure_entity(cluster["type"], cluster["name"], aliases=cluster["aliases"], attributes={**cluster["attributes"], "sources": cluster["sources"], "resolved_from_records": cluster["member_count"]}, normalized=cluster["normalized"])
            for id_type, vals in cluster["identifiers"].items():
                for v in vals:
                    if id_type == "Phone": pid = self._ensure_entity("Phone", v); self._add_relationship(eid, pid, "USES_PHONE", 1.0, 0.98, [{"source": f"FIR:{fir_id}"}])
                    elif id_type == "BankAccount": aid = self._ensure_entity("BankAccount", v); self._add_relationship(eid, aid, "CONTROLS_ACCOUNT", 1.0, 0.95, [{"source": f"FIR:{fir_id}"}])
                    elif id_type == "Vehicle": vid = self._ensure_entity("Vehicle", v); self._add_relationship(eid, vid, "USES_VEHICLE", 1.0, 0.95, [{"source": f"FIR:{fir_id}"}])
            for ctx in cluster["context"]:
                self._case_links.add((eid, ctx, cluster["attributes"].get("role","mentioned")))
        # Narrative relations for this FIR only
        for rel in result.relations:
            sid = self._lookup_entity(rel.source_type, rel.source)
            tid = self._lookup_entity(rel.target_type, rel.target)
            if not sid or not tid or sid == tid: continue
            self._add_relationship(sid, tid, rel.rel_type, 1.0, rel.confidence, [{"source": f"FIR:{fir_id}", "cue": rel.cue, "sentence": rel.sentence[:400]}])
        for name, role in result.roles.items():
            eid = self._lookup_entity("Person", name)
            if eid and eid in self._entities: 
                a = self._entities[eid]["attributes"]; a.setdefault("inferred_roles", []); 
                if role not in a["inferred_roles"]: a["inferred_roles"].append(role)
        # Co-accused for this FIR
        accused_names = [a.get("name") for a in fir.get("accused",[]) if a.get("name")]
        ids = [self._lookup_entity("Person", n) for n in accused_names]; ids=[i for i in ids if i]
        for i in range(len(ids)):
            for j in range(i+1, len(ids)):
                self._add_relationship(ids[i], ids[j], "CO_ACCUSED", 1.0, 0.97, [{"source": f"FIR:{fir_id}", "sections": fir.get("ipc_sections",[])}])
        self.stats.resolution = resolver.stats()
        return resolver

    def add_cdr_batch(self, records: list[dict], recompute: bool = True) -> dict:
        db.init_db(); self._load_existing_state()
        normed = []
        for r in records:
            caller = nz.normalize_phone(r.get("caller") or r.get("caller_number") or r.get("caller_phone") or "")
            callee = nz.normalize_phone(r.get("callee") or r.get("callee_number") or r.get("callee_phone") or "")
            if not caller or not callee: continue
            normed.append({"call_id": r.get("call_id"), "caller": caller, "callee": callee, "ts": r.get("ts") or f"{r.get('call_date','2024-01-01')} {r.get('call_time','12:00:00')}", "duration": int(r.get("duration") or r.get("duration_seconds") or 60), "call_type": r.get("call_type","voice"), "tower_id": r.get("tower_id"), "tower_name": r.get("tower_name") or r.get("tower_location"), "lat": r.get("lat") or _float(r.get("tower_lat")), "lon": r.get("lon") or _float(r.get("tower_lon"))})
        if not normed: return {"added": 0}
        self._persist_cdr(normed)
        # Build edges for new records via DB rebuild of pairs (cheap — CDR table is small)
        # Reuse existing logic but flush via helper
        self._build_cdr_edges_incremental(normed)
        self._flush()
        if recompute:
            analytics = self.enrich(); self._build_search_index()
            log("investigator", "CDR_BATCH", f"{len(normed)} records")
            return {"added": len(normed), "analytics": analytics}
        return {"added": len(normed)}

    def _build_cdr_edges_incremental(self, new_records: list[dict]) -> None:
        # For each new pair, ensure phone entities and CALLED/COMMUNICATED edges
        from collections import Counter
        pairs: dict[tuple[str,str], list[dict]] = {}
        for r in new_records:
            pairs.setdefault((r["caller"], r["callee"]), []).append(r)
        # Load phone->person map from DB
        phone_owner: dict[str,str] = {}
        for row in db.query("SELECT r.source_id, e.name as phone FROM relationships r JOIN entities e ON e.entity_id=r.target_id WHERE r.rel_type='USES_PHONE'"):
            phone_owner[row["phone"]] = row["source_id"]
        # Also consider newly created phone entities in buffer
        for (etype, norm), eid in self._entity_ids.items():
            if etype == "Phone": phone_owner[norm] = eid
        for (caller, callee), recs in pairs.items():
            cid = self._ensure_entity("Phone", caller); eid = self._ensure_entity("Phone", callee)
            weight = min(1.0, 0.3 + 0.1*len(recs))
            self._add_relationship(cid, eid, "CALLED", weight, 0.99, [{"source": "CDR", "call_count": len(recs)}], observations=len(recs))
            a,b = phone_owner.get(caller), phone_owner.get(callee)
            if a and b and a!=b:
                self._add_relationship(a,b, "COMMUNICATED_WITH", min(1.0,0.35+0.09*len(recs)), 0.93, [{"source":"CDR","via_numbers":[caller,callee]}])

    def add_transactions_batch(self, records: list[dict], recompute: bool = True) -> dict:
        db.init_db(); self._load_existing_state()
        normed=[]
        for r in records:
            normed.append({"txn_id": r.get("txn_id"), "ts": r.get("ts") or f"{r.get('date','2024-01-01')} {r.get('time','12:00:00')}", "from_account": nz.normalize_account(r.get("from_account","")) or "CASH", "from_bank": r.get("from_bank"), "from_name": r.get("from_name"), "to_account": nz.normalize_account(r.get("to_account","")) or "CASH", "to_bank": r.get("to_bank"), "to_name": r.get("to_name"), "amount": float(r.get("amount") or r.get("amount_inr") or 0), "txn_type": r.get("txn_type","NEFT"), "description": r.get("description"), "flagged": int(r.get("flagged",0))})
        if not normed: return {"added":0}
        self._persist_transactions(normed)
        # Minimal edge rebuild: just flush accounts and link to persons if names match
        for r in normed:
            fid = self._ensure_entity("BankAccount", r["from_account"]); tid = self._ensure_entity("BankAccount", r["to_account"])
            self._add_relationship(fid, tid, "TRANSFERRED_TO", 0.5, 0.99, [{"source":"BankLedger"}])
            for acc, holder in ((fid, r.get("from_name")), (tid, r.get("to_name"))):
                if holder and holder.upper()!="CASH":
                    pid = self._lookup_entity("Person", nz.normalize_name(holder))
                    if pid: self._add_relationship(pid, acc, "CONTROLS_ACCOUNT", 1.0, 0.9, [{"source":"BankLedger"}])
        self._flush()
        if recompute:
            analytics = self.enrich(); self._build_search_index()
            log("investigator", "LEDGER_BATCH", f"{len(normed)} txns")
            return {"added": len(normed), "analytics": analytics}
        return {"added": len(normed)}

    # ------------------------------------------------------------------
    # Entity extraction + resolution
    # ------------------------------------------------------------------
    def _extract_and_resolve(self, firs: list[dict]) -> EntityResolver:
        # Seed the gazetteer from structured fields — this is what lets the NER
        # reach high recall on Indian names without a trained model.
        people, orgs, locations = set(), set(), set()
        for r in firs:
            for a in r.get("accused", []) or []:
                if a.get("name"):
                    people.add(a["name"])
                if a.get("alias"):
                    people.add(a["alias"])
            comp = r.get("complainant") or {}
            if comp.get("name"):
                people.add(comp["name"])
            for loc in r.get("locations_mentioned", []) or []:
                locations.add(loc)
            if r.get("district"):
                locations.add(r["district"])
            if r.get("state"):
                locations.add(r["state"])

        extractor = EntityExtractor(known_people=people, known_orgs=orgs,
                                    known_locations=locations)
        resolver = EntityResolver()
        extraction_counts: dict[str, int] = defaultdict(int)

        for fir in firs:
            fir_id = fir["fir_id"]
            text = fir.get("description", "") or ""
            result = extractor.extract(text)
            for etype, count in result.counts().items():
                extraction_counts[etype] += count

            # --- structured accused/complainant records (highest trust) ---
            for accused in fir.get("accused", []) or []:
                self._add_person_record(resolver, accused, fir_id, role="accused",
                                        source=f"FIR:{fir_id}")
            comp = fir.get("complainant") or {}
            if comp.get("name"):
                self._add_person_record(resolver, comp, fir_id, role="complainant",
                                        source=f"FIR:{fir_id}")

            # --- unstructured mentions ---
            for ex in result.entities:
                if ex.type == "Person" and ex.extractor.startswith("morph"):
                    resolver.add(Record(
                        rid=f"{fir_id}:mention:{ex.start}", type="Person",
                        name=ex.text, context={fir_id}, source=f"FIR:{fir_id}",
                        attributes={"extraction": ex.extractor, "confidence": ex.confidence},
                    ))

            self._register_fir_entities(fir, result, extractor)

        stats_before = len(resolver.records)
        resolver.resolve()
        self.stats.resolution = resolver.stats()
        self.stats.extraction = dict(extraction_counts)

        # Materialise resolved persons as canonical entities.
        for cluster in resolver.canonical_entities():
            if cluster["type"] not in ("Person", "Organization"):
                continue
            entity_id = self._ensure_entity(
                cluster["type"], cluster["name"],
                aliases=cluster["aliases"],
                attributes={
                    **cluster["attributes"],
                    "sources": cluster["sources"],
                    "resolved_from_records": cluster["member_count"],
                },
                normalized=cluster["normalized"],
            )
            # Link identifiers discovered during resolution.
            for id_type, values in cluster["identifiers"].items():
                for value in values:
                    if id_type == "Phone":
                        pid = self._ensure_entity("Phone", value)
                        self._add_relationship(entity_id, pid, "USES_PHONE", 1.0, 0.98,
                                               [{"source": "structured_field"}])
                    elif id_type == "BankAccount":
                        aid = self._ensure_entity("BankAccount", value)
                        self._add_relationship(entity_id, aid, "CONTROLS_ACCOUNT", 1.0, 0.95,
                                               [{"source": "structured_field"}])
                    elif id_type == "Vehicle":
                        vid = self._ensure_entity("Vehicle", value)
                        self._add_relationship(entity_id, vid, "USES_VEHICLE", 1.0, 0.95,
                                               [{"source": "structured_field"}])
            for fir_id in cluster["context"]:
                role = cluster["attributes"].get("role", "mentioned")
                self._case_links.add((entity_id, fir_id, role))

        # Second pass: relationships extracted from narrative text, mapped onto
        # resolved canonical ids.
        for fir in firs:
            text = fir.get("description", "") or ""
            result = extractor.extract(text)
            for rel in result.relations:
                sid = self._lookup_entity(rel.source_type, rel.source)
                tid = self._lookup_entity(rel.target_type, rel.target)
                if not sid or not tid or sid == tid:
                    continue
                self._add_relationship(
                    sid, tid, rel.rel_type, weight=1.0, confidence=rel.confidence,
                    evidence=[{
                        "source": f"FIR:{fir['fir_id']}",
                        "cue": rel.cue,
                        "sentence": rel.sentence[:400],
                        "extractor": "nlp:relation",
                    }])
            # Roles inferred from command cues.
            for name, role in result.roles.items():
                eid = self._lookup_entity("Person", name)
                if eid and eid in self._entities:
                    attrs = self._entities[eid]["attributes"]
                    attrs.setdefault("inferred_roles", [])
                    if role not in attrs["inferred_roles"]:
                        attrs["inferred_roles"].append(role)

        # Co-accused edges: strongest available association evidence.
        for fir in firs:
            accused = [a.get("name") for a in fir.get("accused", []) or [] if a.get("name")]
            ids = [self._lookup_entity("Person", n) for n in accused]
            ids = [i for i in ids if i]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    self._add_relationship(
                        ids[i], ids[j], "CO_ACCUSED", weight=1.0, confidence=0.97,
                        evidence=[{"source": f"FIR:{fir['fir_id']}",
                                   "sections": fir.get("ipc_sections", []),
                                   "note": "Named as co-accused in the same FIR"}])
        return resolver

    def _add_person_record(self, resolver: EntityResolver, payload: dict,
                           fir_id: str, role: str, source: str) -> None:
        identifiers: dict[str, str] = {}
        phone = nz.normalize_phone(payload.get("phone", ""))
        if phone:
            identifiers["Phone"] = phone
        resolver.add(Record(
            rid=f"{fir_id}:{role}:{payload.get('name')}",
            type="Person",
            name=payload["name"],
            identifiers=identifiers,
            context={fir_id},
            attributes={k: v for k, v in {
                "age": payload.get("age"),
                "gender": payload.get("gender"),
                "alias": payload.get("alias"),
                "address": payload.get("address"),
                "role": role,
            }.items() if v not in (None, "")},
            source=source,
        ))

    def _register_fir_entities(self, fir: dict, result: Any,
                               extractor: EntityExtractor) -> None:
        """Persist non-person entities and their case links."""
        fir_id = fir["fir_id"]

        for vehicle in fir.get("vehicles_involved", []) or []:
            norm = nz.normalize_vehicle(vehicle)
            if norm:
                vid = self._ensure_entity("Vehicle", norm)
                self._case_links.add((vid, fir_id, "involved"))

        for loc in fir.get("locations_mentioned", []) or []:
            lid = self._ensure_entity("Location", loc)
            self._case_links.add((lid, fir_id, "mentioned"))

        for ex in result.entities:
            if ex.type not in PERSISTED_TYPES or ex.type == "Person":
                continue
            eid = self._ensure_entity(ex.type, ex.value if ex.type != "Location" else ex.text)
            self._case_links.add((eid, fir_id, "mentioned"))

    # ------------------------------------------------------------------
    # Derived edges
    # ------------------------------------------------------------------
    def _build_cdr_edges(self) -> None:
        """Phone→Phone CALLED edges, then lift them to Person→Person."""
        pairs: dict[tuple[str, str], dict] = {}
        for row in db.query("SELECT caller, callee, ts, duration FROM cdr"):
            key = (row["caller"], row["callee"])
            item = pairs.setdefault(key, {"count": 0, "duration": 0,
                                          "first": row["ts"], "last": row["ts"]})
            item["count"] += 1
            item["duration"] += row["duration"] or 0
            item["first"] = min(item["first"], row["ts"])
            item["last"] = max(item["last"], row["ts"])

        for (caller, callee), item in pairs.items():
            cid = self._ensure_entity("Phone", caller)
            eid = self._ensure_entity("Phone", callee)
            # Weight grows with frequency but saturates, so one heavy pair does
            # not dominate the graph.
            weight = min(1.0, 0.3 + 0.1 * item["count"])
            self._add_relationship(
                cid, eid, "CALLED", weight=weight, confidence=0.99,
                evidence=[{"source": "CDR", "call_count": item["count"],
                           "total_duration_sec": item["duration"],
                           "first_call": item["first"], "last_call": item["last"]}],
                observations=item["count"], first_seen=item["first"], last_seen=item["last"])

        # Lift to persons through USES_PHONE ownership.
        owner: dict[str, str] = {}
        for key, entity_id in self._entity_ids.items():
            if key[0] != "Phone":
                continue
        for (src, tgt, rel), data in list(self._relationships.items()):
            if rel != "USES_PHONE":
                continue
            phone_entity = self._entities.get(tgt)
            if phone_entity:
                owner[phone_entity["name"]] = src

        for (caller, callee), item in pairs.items():
            a, b = owner.get(caller), owner.get(callee)
            if a and b and a != b:
                self._add_relationship(
                    a, b, "COMMUNICATED_WITH",
                    weight=min(1.0, 0.35 + 0.09 * item["count"]), confidence=0.93,
                    evidence=[{"source": "CDR", "via_numbers": [caller, callee],
                               "call_count": item["count"],
                               "total_duration_sec": item["duration"]}],
                    observations=item["count"])

    def _build_transaction_edges(self) -> None:
        agg: dict[tuple[str, str], dict] = {}
        for row in db.query(
            "SELECT from_account, to_account, from_name, to_name, amount, flagged, ts "
            "FROM transactions"
        ):
            key = (row["from_account"], row["to_account"])
            item = agg.setdefault(key, {"amount": 0.0, "count": 0, "flagged": 0,
                                        "first": row["ts"], "last": row["ts"],
                                        "from_name": row["from_name"],
                                        "to_name": row["to_name"]})
            item["amount"] += float(row["amount"] or 0)
            item["count"] += 1
            item["flagged"] += int(row["flagged"] or 0)
            item["first"] = min(item["first"], row["ts"])
            item["last"] = max(item["last"], row["ts"])

        for (frm, to), item in agg.items():
            fid = self._ensure_entity("BankAccount", frm)
            tid = self._ensure_entity("BankAccount", to)
            self._add_relationship(
                fid, tid, "TRANSFERRED_TO",
                weight=min(1.0, 0.4 + 0.08 * item["count"]),
                confidence=0.99,
                evidence=[{"source": "BankLedger", "total_amount_inr": item["amount"],
                           "transaction_count": item["count"],
                           "flagged_count": item["flagged"],
                           "first": item["first"], "last": item["last"]}],
                observations=item["count"], first_seen=item["first"], last_seen=item["last"])

            # Link account holders named in the ledger to their accounts. This is
            # how a bank dump gets fused with FIR-derived identities.
            for account_id, holder in ((fid, item["from_name"]), (tid, item["to_name"])):
                if not holder or holder.upper() == "CASH":
                    continue
                person_id = self._lookup_entity("Person", nz.normalize_name(holder))
                if person_id:
                    self._add_relationship(person_id, account_id, "CONTROLS_ACCOUNT",
                                           1.0, 0.9,
                                           [{"source": "BankLedger",
                                             "note": f"Account holder name '{holder}' matched a resolved person"}])

        # Lift account transfers to person-level money movement.
        acct_owner: dict[str, str] = {}
        for (src, tgt, rel), _ in list(self._relationships.items()):
            if rel == "CONTROLS_ACCOUNT":
                acct = self._entities.get(tgt)
                if acct:
                    acct_owner[acct["name"]] = src
        for (frm, to), item in agg.items():
            a, b = acct_owner.get(frm), acct_owner.get(to)
            if a and b and a != b:
                self._add_relationship(
                    a, b, "PAID",
                    weight=min(1.0, 0.4 + 0.08 * item["count"]), confidence=0.9,
                    evidence=[{"source": "BankLedger", "via_accounts": [frm, to],
                               "total_amount_inr": item["amount"],
                               "transaction_count": item["count"]}],
                    observations=item["count"])

    def _build_shared_attribute_edges(self) -> None:
        """
        Two people sharing a vehicle, account or tower is investigative signal
        even when no document links them directly.
        """
        shared: dict[tuple[str, str], list[str]] = defaultdict(list)
        by_attribute: dict[str, list[str]] = defaultdict(list)
        for (src, tgt, rel), _ in list(self._relationships.items()):
            if rel in ("USES_VEHICLE", "CONTROLS_ACCOUNT"):
                by_attribute[tgt].append(src)

        for attribute_id, owners in by_attribute.items():
            uniq = sorted(set(owners))
            if len(uniq) < 2:
                continue
            attr = self._entities.get(attribute_id, {})
            rel_type = ("SHARED_VEHICLE" if attr.get("type") == "Vehicle"
                        else "SHARED_ACCOUNT")
            for i in range(len(uniq)):
                for j in range(i + 1, len(uniq)):
                    self._add_relationship(
                        uniq[i], uniq[j], rel_type, weight=0.8, confidence=0.85,
                        evidence=[{"source": "attribute_overlap",
                                   "shared_entity": attr.get("name"),
                                   "shared_type": attr.get("type"),
                                   "note": "Both actors are linked to the same asset"}])

        # Tower co-presence between phone owners.
        tower_users: dict[str, set[str]] = defaultdict(set)
        for row in db.query("SELECT tower_id, caller, callee FROM cdr WHERE tower_id IS NOT NULL"):
            tower_users[row["tower_id"]].add(row["caller"])
            tower_users[row["tower_id"]].add(row["callee"])
        phone_owner: dict[str, str] = {}
        for (src, tgt, rel), _ in list(self._relationships.items()):
            if rel == "USES_PHONE":
                phone = self._entities.get(tgt)
                if phone:
                    phone_owner[phone["name"]] = src
        for tower, numbers in tower_users.items():
            owners = sorted({phone_owner[n] for n in numbers if n in phone_owner})
            if 2 <= len(owners) <= 6:
                for i in range(len(owners)):
                    for j in range(i + 1, len(owners)):
                        self._add_relationship(
                            owners[i], owners[j], "SHARED_TOWER", weight=0.5,
                            confidence=0.6,
                            evidence=[{"source": "CDR:tower", "tower_id": tower,
                                       "note": "Both actors' handsets registered on the same tower"}])

    # ------------------------------------------------------------------
    # Entity/relationship buffers
    # ------------------------------------------------------------------
    def _ensure_entity(self, etype: str, name: str, aliases: list[str] | None = None,
                       attributes: dict | None = None,
                       normalized: str | None = None) -> str:
        norm = normalized or self._normalize_for(etype, name)
        key = (etype, norm)
        if key in self._entity_ids:
            eid = self._entity_ids[key]
            # Hydrate from DB if this is an existing entity not yet in buffer (incremental path)
            if eid not in self._entities:
                row = db.query_one("SELECT * FROM entities WHERE entity_id=?", (eid,))
                if row:
                    self._entities[eid] = {
                        "entity_id": row["entity_id"], "type": row["type"], "name": row["name"],
                        "normalized": row["normalized"], "aliases": db.jload(row["aliases"], []),
                        "attributes": db.jload(row["attributes"], {}), "source_count": row["source_count"] or 0,
                    }
                else:
                    self._entities[eid] = {"entity_id": eid, "type": etype, "name": str(name), "normalized": norm, "aliases": [], "attributes": {}, "source_count": 0}
            if attributes:
                self._entities[eid]["attributes"].update(attributes)
            if aliases:
                existing = set(self._entities[eid]["aliases"])
                self._entities[eid]["aliases"] = sorted(existing | set(aliases))
            self._entities[eid]["source_count"] += 1
            return eid

        self._counters[etype] += 1
        prefix = ENTITY_PREFIX.get(etype, "ENT")
        eid = f"{prefix}-{self._counters[etype]:05d}"
        self._entity_ids[key] = eid
        self._entities[eid] = {
            "entity_id": eid, "type": etype, "name": str(name),
            "normalized": norm, "aliases": sorted(aliases or []),
            "attributes": dict(attributes or {}), "source_count": 1,
        }
        self.stats.entities_created[etype] = self.stats.entities_created.get(etype, 0) + 1
        return eid

    def _lookup_entity(self, etype: str, name: str) -> str | None:
        return self._entity_ids.get((etype, self._normalize_for(etype, name)))

    @staticmethod
    def _normalize_for(etype: str, name: str) -> str:
        if etype in ("Person", "Organization"):
            return nz.normalize_name(name)
        if etype == "Location":
            return nz.normalize_location(name)
        if etype == "Phone":
            return nz.normalize_phone(name) or str(name)
        if etype == "Vehicle":
            return nz.normalize_vehicle(name) or str(name).upper()
        if etype == "BankAccount":
            return nz.normalize_account(name) or str(name)
        return str(name).strip().upper()

    def _add_relationship(self, source: str, target: str, rel_type: str,
                          weight: float, confidence: float, evidence: list[dict],
                          observations: int = 1, first_seen: str | None = None,
                          last_seen: str | None = None) -> None:
        if source == target:
            return
        key = (source, target, rel_type)
        reverse = (target, source, rel_type)
        # Undirected semantics for symmetric relationship types.
        if rel_type in ("CO_ACCUSED", "ASSOCIATE_OF", "CO_MENTIONED", "SHARED_TOWER",
                        "SHARED_VEHICLE", "SHARED_ACCOUNT", "COMMUNICATED_WITH",
                        "CONSPIRED_WITH", "MET_WITH", "LINKED_TO"):
            if reverse in self._relationships:
                key = reverse

        existing = self._relationships.get(key)
        if existing:
            existing["weight"] = max(existing["weight"], weight)
            existing["confidence"] = max(existing["confidence"], confidence)
            existing["observations"] += observations
            existing["evidence"].extend(evidence)
            if first_seen:
                existing["first_seen"] = min(existing["first_seen"] or first_seen, first_seen)
            if last_seen:
                existing["last_seen"] = max(existing["last_seen"] or last_seen, last_seen)
            return

        self._relationships[key] = {
            "source_id": key[0], "target_id": key[1], "rel_type": rel_type,
            "weight": weight, "confidence": confidence, "evidence": list(evidence),
            "observations": observations, "first_seen": first_seen, "last_seen": last_seen,
        }
        self.stats.relationships_created[rel_type] = \
            self.stats.relationships_created.get(rel_type, 0) + 1

    def _flush(self) -> None:
        db.executemany(
            "INSERT OR REPLACE INTO entities (entity_id, type, name, normalized, aliases, "
            "attributes, source_count) VALUES (?,?,?,?,?,?,?)",
            [(e["entity_id"], e["type"], e["name"], e["normalized"],
              db.jdump(e["aliases"]), db.jdump(e["attributes"]), e["source_count"])
             for e in self._entities.values()])

        db.executemany(
            "INSERT OR REPLACE INTO relationships (source_id, target_id, rel_type, weight, "
            "confidence, evidence, observations, first_seen, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(r["source_id"], r["target_id"], r["rel_type"], r["weight"], r["confidence"],
              db.jdump(r["evidence"][:12]), r["observations"], r["first_seen"], r["last_seen"])
             for r in self._relationships.values()])

        db.executemany(
            "INSERT OR REPLACE INTO entity_cases (entity_id, fir_id, role) VALUES (?,?,?)",
            sorted(self._case_links))

    # ------------------------------------------------------------------
    # Enrichment: graph analytics -> patterns -> risk -> alerts
    # ------------------------------------------------------------------
    def enrich(self) -> dict:
        from app.alerts.rules import generate_alerts
        from app.analytics.patterns import run_all_detectors
        from app.ml.risk import RiskScorer

        engine.load()
        communities = engine.communities()
        db.execute("DELETE FROM communities")
        db.executemany(
            "INSERT OR REPLACE INTO communities (community_id, entity_id, label, cohesion) "
            "VALUES (?,?,?,?)",
            [(c["community_id"], member, f"Cell-{c['community_id']:02d}", c["insularity"])
             for c in communities["communities"] for member in c["members"]])

        patterns = run_all_detectors(persist=True)

        metrics = engine.centrality(person_only=True)
        risk = RiskScorer(graph_metrics=metrics).score_all(persist=True)

        kingpins = engine.kingpin_ranking(top_n=0)
        db.executemany(
            "UPDATE entities SET kingpin_score=? WHERE entity_id=?",
            [(k["kingpin_score"], k["entity_id"]) for k in kingpins])

        engine.load()   # reload so scores are visible in graph payloads
        engine.communities()
        alerts = generate_alerts()

        return {
            "graph": {
                "nodes": engine.G.number_of_nodes(),
                "edges": engine.G.number_of_edges(),
                "person_nodes": len([n for n, d in engine.G.nodes(data=True)
                                     if d.get("type") == "Person"]),
                "communities": communities["count"],
                "modularity": communities["modularity"],
            },
            "patterns": {"total": patterns["total"], "by_type": patterns["by_type"],
                         "by_severity": patterns["by_severity"]},
            "risk": {
                "scored": len(risk),
                "critical": len([r for r in risk if r["risk_band"] == "Critical"]),
                "high": len([r for r in risk if r["risk_band"] == "High"]),
                "top_5": [{"name": r["name"], "score": r["risk_score"]} for r in risk[:5]],
            },
            "kingpins": {
                "top_5": [{"name": k["name"], "score": k["kingpin_score"],
                           "tier": k["tier"]} for k in kingpins[:5]],
            },
            "alerts": alerts,
        }

    # ------------------------------------------------------------------
    def _build_search_index(self) -> None:
        db.execute("DELETE FROM search_index")
        rows: list[tuple] = []

        for row in db.query(
            "SELECT entity_id, type, name, aliases, attributes, risk_score FROM entities"
        ):
            aliases = " ".join(db.jload(row["aliases"], []))
            attrs = db.jload(row["attributes"], {})
            body = " ".join(str(v) for v in attrs.values() if isinstance(v, (str, int, float)))
            rows.append((row["entity_id"], "entity", row["name"],
                         f"{aliases} {body}".strip(),
                         db.jdump({"type": row["type"], "risk_score": row["risk_score"]})))

        for row in db.query(
            "SELECT fir_id, title, description, station, district, state, "
            "ipc_sections, crime_type FROM cases"
        ):
            rows.append((row["fir_id"], "case", row["title"] or row["fir_id"],
                         f"{row['description']} {row['station']} {row['district']} "
                         f"{row['state']} {' '.join(db.jload(row['ipc_sections'], []))}",
                         db.jdump({"crime_type": row["crime_type"], "state": row["state"]})))

        for row in db.query("SELECT id, pattern_type, typology, summary, severity FROM patterns"):
            rows.append((f"PAT-{row['id']}", "pattern", row["typology"], row["summary"],
                         db.jdump({"pattern_type": row["pattern_type"],
                                   "severity": row["severity"]})))

        db.executemany(
            "INSERT INTO search_index (ref_id, ref_type, title, body, meta) VALUES (?,?,?,?,?)",
            rows)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def run_pipeline(**kwargs: Any) -> dict:
    return Pipeline().run(**kwargs)
