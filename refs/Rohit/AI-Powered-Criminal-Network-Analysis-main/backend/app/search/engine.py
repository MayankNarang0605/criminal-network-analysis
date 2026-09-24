"""
Full-text search over entities, cases and pattern findings.

Uses SQLite FTS5 with BM25 ranking — the same ranking family Elasticsearch uses
by default — so relevance ordering is meaningful rather than a LIKE scan. Also
provides a fuzzy fallback for misspelt Indian names, which is the dominant
real-world query failure mode.
"""
from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz, process

from app import db
from app.nlp import normalize as nz

FTS_SPECIAL = re.compile(r'["*(){}\[\]^~:\\-]')


def _sanitise(query: str) -> str:
    """Escape FTS5 operators so user input cannot break the MATCH expression."""
    cleaned = FTS_SPECIAL.sub(" ", query or "").strip()
    terms = [t for t in cleaned.split() if t]
    if not terms:
        return ""
    # Prefix-match the final term for type-ahead behaviour.
    return " ".join(f'"{t}"' for t in terms[:-1] + [terms[-1] + "*"])


def search(query: str, ref_type: str | None = None, limit: int = 25) -> dict[str, Any]:
    match_expr = _sanitise(query)
    results: list[dict] = []

    if match_expr:
        sql = ("SELECT ref_id, ref_type, title, body, meta, bm25(search_index) AS score "
               "FROM search_index WHERE search_index MATCH ?")
        params: list[Any] = [match_expr]
        if ref_type:
            sql += " AND ref_type = ?"
            params.append(ref_type)
        sql += " ORDER BY score LIMIT ?"
        params.append(limit)
        try:
            for row in db.query(sql, params):
                results.append({
                    "ref_id": row["ref_id"],
                    "ref_type": row["ref_type"],
                    "title": row["title"],
                    "snippet": _snippet(row["body"], query),
                    "meta": db.jload(row["meta"], {}),
                    # bm25 returns negative values where lower is better.
                    "relevance": round(-float(row["score"] or 0), 4),
                    "match_type": "full_text",
                })
        except Exception:
            results = []

    fuzzy: list[dict] = []
    if len(results) < 5:
        fuzzy = _fuzzy_fallback(query, limit=limit - len(results))
        seen = {r["ref_id"] for r in results}
        fuzzy = [f for f in fuzzy if f["ref_id"] not in seen]

    combined = results + fuzzy
    return {
        "query": query,
        "total": len(combined),
        "full_text_hits": len(results),
        "fuzzy_hits": len(fuzzy),
        "results": combined,
        "engine": "SQLite FTS5 (BM25) with Jaro-Winkler fuzzy fallback",
    }


def _fuzzy_fallback(query: str, limit: int = 10) -> list[dict]:
    """
    Name search that tolerates transliteration variance: 'Vikaram Desai',
    'Vikram Desayi' and 'V. Desai' should all find 'Vikram Desai'.
    """
    if not query or limit <= 0:
        return []
    candidates = {r["entity_id"]: r for r in db.query(
        "SELECT entity_id, name, type, risk_score, kingpin_score, aliases FROM entities")}
    if not candidates:
        return []

    choices: dict[str, str] = {}
    for eid, row in candidates.items():
        choices[eid] = row["name"]
        for alias in db.jload(row["aliases"], []):
            choices[f"{eid}::{alias}"] = alias

    matches = process.extract(query, choices, scorer=fuzz.WRatio, limit=limit * 2, score_cutoff=70)
    out: list[dict] = []
    seen: set[str] = set()
    for matched_name, score, key in matches:
        eid = str(key).split("::")[0]
        if eid in seen:
            continue
        seen.add(eid)
        row = candidates.get(eid)
        if not row:
            continue
        out.append({
            "ref_id": eid,
            "ref_type": "entity",
            "title": row["name"],
            "snippet": (f"Matched '{matched_name}' at {score:.0f}% similarity "
                        f"({row['type']}, risk {row['risk_score']:.0f})"),
            "meta": {"type": row["type"], "risk_score": row["risk_score"],
                     "kingpin_score": row["kingpin_score"]},
            "relevance": round(score / 100.0, 4),
            "match_type": "fuzzy_name",
        })
        if len(out) >= limit:
            break
    return out


def _snippet(body: str, query: str, window: int = 160) -> str:
    text = nz.squash(body or "")
    if not text:
        return ""
    terms = [t for t in re.split(r"\W+", query or "") if len(t) > 2]
    lower = text.lower()
    for term in terms:
        idx = lower.find(term.lower())
        if idx >= 0:
            lo = max(0, idx - window // 2)
            hi = min(len(text), idx + window // 2)
            return ("…" if lo else "") + text[lo:hi] + ("…" if hi < len(text) else "")
    return text[:window] + ("…" if len(text) > window else "")


def suggest(prefix: str, limit: int = 10) -> list[dict]:
    """Type-ahead suggestions across entity names."""
    if not prefix or len(prefix) < 2:
        return []
    like = f"{prefix}%"
    rows = db.query(
        "SELECT entity_id, name, type, risk_score FROM entities "
        "WHERE name LIKE ? ORDER BY risk_score DESC LIMIT ?", (like, limit))
    if len(rows) >= limit:
        return [dict(r) for r in rows]
    contains = db.query(
        "SELECT entity_id, name, type, risk_score FROM entities "
        "WHERE name LIKE ? AND name NOT LIKE ? ORDER BY risk_score DESC LIMIT ?",
        (f"%{prefix}%", like, limit - len(rows)))
    return [dict(r) for r in list(rows) + list(contains)]
