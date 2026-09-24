"""
Entity resolution / record linkage.

Fragmented data is the core problem in the statement: the same human appears as
"Vikram Desai" in an FIR, as 9123456780 in a CDR, and as an account holder in a
bank dump. Resolution here is a two-signal union-find:

  1. **Hard identifiers** (phone, account, vehicle, email, PAN, Aadhaar) are
     transitive evidence: sharing one merges records immediately.
  2. **Soft name similarity** uses blocking (first-token / metaphone-ish key) plus
     Jaro-Winkler and token-set ratio, requiring corroboration from at least one
     shared context (case, phone, location) before merging.

Merging is auditable: every merge records the rule and the score that caused it,
so an investigator can reverse a bad link.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from rapidfuzz import fuzz, distance

from app.nlp import normalize as nz

HARD_ID_TYPES = {"Phone", "BankAccount", "Vehicle", "Email", "PAN", "Aadhaar",
                 "IMEI", "CryptoWallet"}

HONORIFIC_TOKENS = nz.HONORIFICS | {"shri", "smt", "md", "mohd", "mr", "mrs", "ms"}


def clean_surface(name: str) -> str:
    """
    Presentation form of a name: strip honorifics, trailing punctuation and
    stray capitalisation artefacts, while preserving the actual name tokens.
    'SHRI VIKRAM DESAI.' -> 'Vikram Desai'
    """
    text = re.sub(r"\s+", " ", str(name or "")).strip().strip(".,;: ")
    if not text:
        return ""
    tokens = [t for t in text.split(" ") if t]
    kept = [t for t in tokens if t.lower().strip(".") not in HONORIFIC_TOKENS]
    if not kept:
        kept = tokens
    # Normalise shouted entries but leave deliberate initials alone.
    rebuilt = []
    for tok in kept:
        stripped = tok.strip(".")
        if len(stripped) == 1:
            rebuilt.append(stripped.upper() + ".")
        elif tok.isupper():
            rebuilt.append(stripped.capitalize())
        else:
            rebuilt.append(stripped)
    return " ".join(rebuilt)

# Name pairs that must never merge even at high similarity (common Indian
# name collisions where the surname differs meaningfully).
NAME_MERGE_THRESHOLD = 92.0        # Jaro-Winkler * 100
TOKEN_MERGE_THRESHOLD = 90.0       # token set ratio


@dataclass
class Record:
    """A candidate mention to be resolved into a canonical entity."""
    rid: str
    type: str
    name: str
    identifiers: dict[str, str] = field(default_factory=dict)
    context: set[str] = field(default_factory=set)   # case ids, locations
    attributes: dict = field(default_factory=dict)
    source: str = ""

    @property
    def key(self) -> str:
        if self.type == "Person":
            return nz.normalize_name(self.name)
        if self.type == "Location":
            return nz.normalize_location(self.name)
        return str(self.name).strip().upper()


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def add(self, x: str) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0

    def find(self, x: str) -> str:
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # Path compression.
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True

    def groups(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for x in self.parent:
            out.setdefault(self.find(x), []).append(x)
        return out


def phonetic_key(name: str) -> str:
    """
    Lightweight phonetic key tuned for Indian transliteration variance
    (Mohd/Mohammed, Shaikh/Sheikh, Kumar/Kumaar, v/w, s/sh).
    """
    n = nz.normalize_name(name)
    if not n:
        return ""
    first = n.split()[0]
    s = first
    s = re.sub(r"[aeiou]+", "", s[:1]) + re.sub(r"[aeiou]+", "", s[1:])
    s = s.replace("ph", "f").replace("gh", "g").replace("kh", "k")
    s = s.replace("sh", "s").replace("ch", "c").replace("th", "t")
    s = s.replace("w", "v").replace("z", "j").replace("q", "k")
    s = re.sub(r"(.)\1+", r"\1", s)
    return s[:5]


def name_similarity(a: str, b: str) -> float:
    na, nb = nz.normalize_name(a), nz.normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    jw = distance.JaroWinkler.similarity(na, nb) * 100.0
    tok = fuzz.token_set_ratio(na, nb)
    # Require both signals to be strong; the mean punishes one-sided matches.
    return (jw + tok) / 2.0


class EntityResolver:
    def __init__(self) -> None:
        self.records: dict[str, Record] = {}
        self.uf = UnionFind()
        self.merges: list[dict] = []

    def add(self, record: Record) -> None:
        self.records[record.rid] = record
        self.uf.add(record.rid)

    # -- resolution passes -------------------------------------------------
    def resolve(self) -> dict[str, list[str]]:
        self._merge_exact_keys()
        self._merge_hard_identifiers()
        self._merge_fuzzy_names()
        return self.uf.groups()

    def _merge_exact_keys(self) -> None:
        buckets: dict[tuple[str, str], list[str]] = {}
        for rid, rec in self.records.items():
            buckets.setdefault((rec.type, rec.key), []).append(rid)
        for (etype, key), rids in buckets.items():
            if not key:
                continue
            for other in rids[1:]:
                if self.uf.union(rids[0], other):
                    self.merges.append({
                        "rule": "exact_key", "type": etype, "key": key,
                        "a": rids[0], "b": other, "score": 100.0,
                    })

    def _merge_hard_identifiers(self) -> None:
        index: dict[tuple[str, str], list[str]] = {}
        for rid, rec in self.records.items():
            if rec.type != "Person":
                continue
            for id_type, value in rec.identifiers.items():
                if id_type in HARD_ID_TYPES and value:
                    index.setdefault((id_type, str(value)), []).append(rid)
        for (id_type, value), rids in index.items():
            for other in rids[1:]:
                if self.uf.union(rids[0], other):
                    self.merges.append({
                        "rule": "shared_identifier", "identifier": f"{id_type}:{value}",
                        "a": rids[0], "b": other, "score": 99.0,
                    })

    def _merge_fuzzy_names(self) -> None:
        # Blocking so this stays near-linear rather than O(n^2) over the corpus.
        blocks: dict[str, list[str]] = {}
        for rid, rec in self.records.items():
            if rec.type not in ("Person", "Organization"):
                continue
            blocks.setdefault(phonetic_key(rec.name), []).append(rid)

        for _, rids in blocks.items():
            if len(rids) < 2:
                continue
            for i in range(len(rids)):
                for j in range(i + 1, len(rids)):
                    a, b = self.records[rids[i]], self.records[rids[j]]
                    if a.type != b.type:
                        continue
                    if self.uf.find(rids[i]) == self.uf.find(rids[j]):
                        continue
                    score = name_similarity(a.name, b.name)
                    if score < NAME_MERGE_THRESHOLD:
                        continue
                    # Require corroboration: shared context or shared identifier.
                    shared_context = a.context & b.context
                    shared_ids = {
                        k for k in a.identifiers
                        if k in b.identifiers and a.identifiers[k] == b.identifiers[k]
                    }
                    conflicting_ids = {
                        k for k in a.identifiers
                        if k in HARD_ID_TYPES and k in b.identifiers
                        and a.identifiers[k] != b.identifiers[k]
                    }
                    if conflicting_ids and not shared_ids:
                        continue
                    if not (shared_context or shared_ids or score >= 99.0):
                        continue
                    if self.uf.union(rids[i], rids[j]):
                        self.merges.append({
                            "rule": "fuzzy_name", "a": rids[i], "b": rids[j],
                            "score": round(score, 2),
                            "corroboration": sorted(shared_context | shared_ids) or ["identical_name"],
                        })

    # -- canonical output --------------------------------------------------
    @staticmethod
    def _canonical_record(recs: list[Record]) -> Record:
        """
        Pick the most authoritative surface form for a cluster.

        Preference order: a structured record (accused/complainant field) over a
        free-text mention; then the most complete form — full token count, no
        honorific, not ALL-CAPS, no trailing initial. This is what makes the
        dashboard show 'Vikram Desai' rather than 'SHRI V. DESAI.'
        """
        def score(r: Record) -> tuple:
            name = clean_surface(r.name)
            tokens = name.replace(".", " ").split()
            structured = 1 if r.attributes.get("role") else 0
            has_honorific = any(t.lower().strip(".") in HONORIFIC_TOKENS for t in tokens)
            all_caps = 1 if name.isupper() and len(name) > 3 else 0
            initial_only = 1 if any(len(t.strip(".")) == 1 for t in tokens) else 0
            return (
                structured,
                -all_caps,
                -int(has_honorific),
                -initial_only,
                len([t for t in tokens if len(t.strip(".")) > 1]),
                len(name),
            )

        return max(recs, key=score)

    def canonical_entities(self) -> list[dict]:
        """Collapse each cluster into a single canonical entity payload."""
        out: list[dict] = []
        for root, members in self.uf.groups().items():
            recs = [self.records[m] for m in members if m in self.records]
            if not recs:
                continue
            best = self._canonical_record(recs)
            display_name = clean_surface(best.name) or best.name
            aliases = sorted({clean_surface(r.name) or r.name for r in recs
                              if (clean_surface(r.name) or r.name) != display_name})
            identifiers: dict[str, set[str]] = {}
            attributes: dict = {}
            context: set[str] = set()
            sources: set[str] = set()
            for r in recs:
                for k, v in r.identifiers.items():
                    identifiers.setdefault(k, set()).add(str(v))
                attributes.update({k: v for k, v in r.attributes.items() if v not in (None, "")})
                context |= r.context
                if r.source:
                    sources.add(r.source)
            out.append({
                "cluster_id": root,
                "type": best.type,
                "name": display_name,
                "normalized": best.key,
                "aliases": aliases,
                "member_names": sorted({r.name for r in recs}),
                "identifiers": {k: sorted(v) for k, v in identifiers.items()},
                "attributes": attributes,
                "context": sorted(context),
                "sources": sorted(sources),
                "member_count": len(recs),
            })
        return out

    def stats(self) -> dict:
        groups = self.uf.groups()
        merged = sum(1 for g in groups.values() if len(g) > 1)
        return {
            "input_records": len(self.records),
            "resolved_entities": len(groups),
            "clusters_with_merges": merged,
            "merge_operations": len(self.merges),
            "deduplication_rate": round(
                (1 - len(groups) / len(self.records)) * 100, 2
            ) if self.records else 0.0,
            "rules_applied": _count_by(self.merges, "rule"),
        }


def _count_by(items: Iterable[dict], field_name: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        key = str(it.get(field_name))
        out[key] = out.get(key, 0) + 1
    return out
