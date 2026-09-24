import React from "react";
import { api } from "../lib/api";
import { Card, Chip, ErrorBox, Loading, PageHead, Stat, fmtNum, useApi } from "../components/ui";

/**
 * Live Investigation — add FIR/CDR/Ledger directly from the dashboard.
 *
 * No file editing. Type a case here, submit, and the
 * graph/risk/patterns recompute immediately (additive ingest, no wipe).
 * Three tabs: FIR, CDR batch, Ledger batch. Narrative has live extraction
 * preview so the AI is demonstrable before you even submit.
 */
export default function LiveInvestigation({ onNavigate }) {
  const [active, setActive] = React.useState("fir");
  const stats = useApi(() => api.stats());
  return (
    <>
      <PageHead
        title="Live Investigation"
        desc="Add a new FIR, CDR records or ledger entries from the dashboard — no file editing. Cases appear in the graph, risk ranking and audit trail within seconds. Additive only; existing data is never wiped."
        actions={
          <div className="row" style={{ gap: 8 }}>
            <span className="chip chip-neutral">{fmtNum(stats.data?.cases)} cases · {fmtNum(stats.data?.entities)} entities</span>
            <button className="btn btn-sm" onClick={stats.refresh}>Refresh counts</button>
          </div>
        }
      />

      <div className="tabs" style={{ marginBottom: 14 }}>
        {[
          { id: "fir", label: "New FIR" },
          { id: "cdr", label: "CDR Batch" },
          { id: "ledger", label: "Ledger Batch" },
        ].map((t) => (
          <button key={t.id} className={`tab ${active === t.id ? "active" : ""}`} onClick={() => setActive(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {active === "fir" && <FirTab onNavigate={onNavigate} onDone={stats.refresh} />}
      {active === "cdr" && <CdrTab onDone={stats.refresh} />}
      {active === "ledger" && <LedgerTab onDone={stats.refresh} />}
    </>
  );
}

function FirTab({ onNavigate, onDone }) {
  const [firId, setFirId] = React.useState(`FIR-2024-XX-${String(Math.floor(Math.random() * 90000) + 10000)}`);
  const [station, setStation] = React.useState("Test PS");
  const [district, setDistrict] = React.useState("Pune");
  const [state, setState] = React.useState("Maharashtra");
  const [sections, setSections] = React.useState("420, 120B");
  const [crimeType, setCrimeType] = React.useState("Economic Offence");
  const [priority, setPriority] = React.useState("High");
  const [dateFiled, setDateFiled] = React.useState("2024-08-01");
  const [officer, setOfficer] = React.useState("Inspector Demo");
  const [accusedRows, setAccusedRows] = React.useState([
    { name: "Amit Rao", phone: "9876543210", alias: "", vehicle: "MH01AB1234", age: "32" },
    { name: "Sunita Devi", phone: "9876543211", alias: "", vehicle: "", age: "28" },
  ]);
  const [description, setDescription] = React.useState(
    "Accused Amit Rao (9876543210) along with associate Sunita Devi conspired to defraud complainant of Rs 18 lakh via Axis account 912345678901 transferred to HDFC 50198765432 using vehicle MH01AB1234. Amit Rao coordinates the network and Sunita Devi handles recruitment."
  );
  const [preview, setPreview] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [result, setResult] = React.useState(null);

  async function doPreview() {
    setError(null);
    try {
      const r = await api.extract(description);
      setPreview(r);
    } catch (e) {
      setError(e);
    }
  }

  async function submit() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const accused = accusedRows
        .filter((r) => r.name.trim())
        .map((r) => ({
          name: r.name.trim(),
          phone: r.phone.trim() || undefined,
          alias: r.alias.trim() || undefined,
          vehicle: r.vehicle.trim() || undefined,
          age: r.age ? Number(r.age) : undefined,
          gender: "Male",
        }));
      const payload = {
        fir_id: firId.trim(),
        station,
        district,
        state,
        date_filed: dateFiled,
        ipc_sections: sections
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        crime_type: crimeType,
        priority,
        status: "Under Investigation",
        investigating_officer: officer,
        description,
        accused,
        locations_mentioned: [district, station],
        vehicles_involved: accusedRows.map((r) => r.vehicle).filter(Boolean),
      };
      const res = await api.addCase(payload);
      setResult(res);
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="stack">
        <Card title="FIR Details" note="Required: FIR ID must be unique. Phone/vehicle/account are optional but drive linking.">
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <label className="field">
              <span>FIR ID *</span>
              <input className="input" value={firId} onChange={(e) => setFirId(e.target.value)} placeholder="FIR-2024-XX-00001" />
            </label>
            <label className="field">
              <span>Date Filed</span>
              <input className="input" type="date" value={dateFiled} onChange={(e) => setDateFiled(e.target.value)} />
            </label>
            <label className="field">
              <span>Station</span>
              <input className="input" value={station} onChange={(e) => setStation(e.target.value)} />
            </label>
            <label className="field">
              <span>District</span>
              <input className="input" value={district} onChange={(e) => setDistrict(e.target.value)} />
            </label>
            <label className="field">
              <span>State</span>
              <input className="input" value={state} onChange={(e) => setState(e.target.value)} />
            </label>
            <label className="field">
              <span>IPC Sections (comma)</span>
              <input className="input" value={sections} onChange={(e) => setSections(e.target.value)} placeholder="420, 120B, 370" />
            </label>
            <label className="field">
              <span>Crime Type</span>
              <input className="input" value={crimeType} onChange={(e) => setCrimeType(e.target.value)} />
            </label>
            <label className="field">
              <span>Priority</span>
              <select className="input" value={priority} onChange={(e) => setPriority(e.target.value)}>
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </label>
          </div>
          <label className="field" style={{ marginTop: 10 }}>
            <span>Investigating Officer</span>
            <input className="input" value={officer} onChange={(e) => setOfficer(e.target.value)} />
          </label>
        </Card>

        <Card
          title="Accused (repeatable rows)"
          note="Phone is the strongest linking signal — if you enter a phone that already exists (e.g., Priya Nair 9234567891), resolution will merge and show Alias."
          actions={
            <button className="btn btn-sm" onClick={() => setAccusedRows((r) => [...r, { name: "", phone: "", alias: "", vehicle: "", age: "" }])}>
              + Add row
            </button>
          }
        >
          {accusedRows.map((row, i) => (
            <div key={i} className="grid" style={{ gridTemplateColumns: "1.2fr 1fr 0.8fr 1fr 0.5fr auto", gap: 6, marginBottom: 6 }}>
              <input className="input" placeholder="Name *" value={row.name} onChange={(e) => setAccusedRows((a) => a.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
              <input className="input" placeholder="Phone" value={row.phone} onChange={(e) => setAccusedRows((a) => a.map((x, j) => (j === i ? { ...x, phone: e.target.value } : x)))} />
              <input className="input" placeholder="Alias" value={row.alias} onChange={(e) => setAccusedRows((a) => a.map((x, j) => (j === i ? { ...x, alias: e.target.value } : x)))} />
              <input className="input" placeholder="Vehicle" value={row.vehicle} onChange={(e) => setAccusedRows((a) => a.map((x, j) => (j === i ? { ...x, vehicle: e.target.value } : x)))} />
              <input className="input" placeholder="Age" value={row.age} onChange={(e) => setAccusedRows((a) => a.map((x, j) => (j === i ? { ...x, age: e.target.value } : x)))} />
              <button className="btn btn-sm" onClick={() => setAccusedRows((a) => a.filter((_, j) => j !== i))} disabled={accusedRows.length === 1}>
                ×
              </button>
            </div>
          ))}
        </Card>

        <Card title="Narrative" note="Free text — enter the FIR narrative. Click Preview to show AI highlights BEFORE submitting (proves extractor on unseen text).">
          <textarea className="input" style={{ minHeight: 140 }} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Accused ... 9876543210 used MH01AB1234 to transfer Rs 18 lakh via Axis..." />
          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn btn-sm" onClick={doPreview} disabled={!description.trim()}>
              Preview Extraction
            </button>
            <span className="dim" style={{ fontSize: 11 }}>
              Shows phones/plates/accounts/IPC found with character offsets — same engine at nlp/extractor.py:32
            </span>
          </div>
          {preview && (
            <div style={{ marginTop: 10 }}>
              <div className="row" style={{ gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
                {Object.entries(preview.counts || {}).map(([k, v]) => (
                  <span key={k} className="chip chip-neutral">
                    {k}: {v}
                  </span>
                ))}
              </div>
              <div style={{ maxHeight: 160, overflow: "auto", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 6, padding: 8 }}>
                <HighlightedPreview text={description} entities={preview.entities || []} />
              </div>
              {preview.relations?.length > 0 && (
                <div style={{ marginTop: 6, fontSize: 12 }}>
                  Relations: {preview.relations.map((r) => `${r.source} —[${r.rel_type}]→ ${r.target}`).join(", ")}
                </div>
              )}
            </div>
          )}
        </Card>

        {error && <ErrorBox error={error} />}
        <div className="row">
          <button className="btn btn-primary" onClick={submit} disabled={busy} style={{ minWidth: 160 }}>
            {busy ? "Adding & Recomputing…" : "Add FIR to Graph"}
          </button>
          <span className="dim" style={{ fontSize: 11 }}>Additive only — existing 33 cases stay. Audit logs CASE_CREATED.</span>
        </div>
        {result && (
          <Card title="Added — What Happened" note={`FIR ${result.fir_id} ingested, graph recomputed. Click to inspect.`}>
            <div style={{ marginBottom: 8 }}>
              {result.created_entities?.map((c) => (
                <div key={c.entity_id} style={{ marginBottom: 4 }}>
                  <button className="btn btn-sm" onClick={() => onNavigate("entity", c.entity_id)}>
                    Open {c.name} ({c.entity_id})
                  </button>
                  <span className="dim" style={{ marginLeft: 8, fontSize: 11 }}>
                    Phone: {c.input?.phone || "—"}
                  </span>
                </div>
              ))}
            </div>
            <div className="row" style={{ gap: 6 }}>
              <button className="btn btn-sm" onClick={() => onNavigate("case", result.fir_id)}>
                View FIR
              </button>
              <button className="btn btn-sm" onClick={() => onNavigate("graph", result.created_entities?.[0]?.entity_id)}>
                View in Graph
              </button>
              <button className="btn btn-sm" onClick={() => onNavigate("dashboard")}>
                Dashboard (new counts)
              </button>
            </div>
            <div className="dim" style={{ fontSize: 11, marginTop: 8 }}>
              Merges: {result.resolution?.merge_operations ?? 0} · Patterns: {result.analytics?.patterns?.total ?? "—"} · Nodes now: {result.analytics?.graph?.nodes ?? "—"}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function CdrTab({ onDone }) {
  const [text, setText] = React.useState("9876543210, 9123456789, 2024-06-01 14:30:00, 120\n9234567891, 9876543210, 2024-06-02 09:15:00, 300");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [res, setRes] = React.useState(null);
  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const records = text
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .map((line) => {
          const [caller, callee, ts, duration] = line.split(",").map((s) => s.trim());
          return { caller, callee, ts, duration: Number(duration) || 60 };
        });
      const r = await api.addCdrBatch(records);
      setRes(r);
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="CDR Batch" note="Format per line: caller, callee, ts (YYYY-MM-DD HH:MM:SS), duration_sec. Creates CALLED + COMMUNICATED_WITH edges.">
      <textarea className="input" style={{ minHeight: 120, fontFamily: "monospace", fontSize: 12 }} value={text} onChange={(e) => setText(e.target.value)} />
      {error && <ErrorBox error={error} />}
      <button className="btn btn-primary" onClick={submit} disabled={busy} style={{ marginTop: 8 }}>
        {busy ? "Adding…" : "Add CDR Records"}
      </button>
      {res && <div className="dim" style={{ marginTop: 6 }}>Added {res.added} records. Graph edges + risk recomputed.</div>}
    </Card>
  );
}

function LedgerTab({ onDone }) {
  const [text, setText] = React.useState("30142567890, SBI, Amit Rao, 50198765432, HDFC, Priya Nair, 1800000, NEFT\n912345678901, Axis, Amit Rao, 50198765432, HDFC, Sunita, 950000, RTGS");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [res, setRes] = React.useState(null);
  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const records = text
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .map((line) => {
          const [from_account, from_bank, from_name, to_account, to_bank, to_name, amount, txn_type] = line.split(",").map((s) => s.trim());
          return { from_account, from_bank, from_name, to_account, to_bank, to_name, amount: Number(amount) || 0, txn_type: txn_type || "NEFT" };
        });
      const r = await api.addTransactionsBatch(records);
      setRes(r);
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Ledger Batch" note="Format per line: from_account, from_bank, from_name, to_account, to_bank, to_name, amount, txn_type">
      <textarea className="input" style={{ minHeight: 120, fontFamily: "monospace", fontSize: 12 }} value={text} onChange={(e) => setText(e.target.value)} />
      {error && <ErrorBox error={error} />}
      <button className="btn btn-primary" onClick={submit} disabled={busy} style={{ marginTop: 8 }}>
        {busy ? "Adding…" : "Add Ledger Entries"}
      </button>
      {res && <div className="dim" style={{ marginTop: 6 }}>Added {res.added} entries. Patterns (layering/structuring) recomputed.</div>}
    </Card>
  );
}

function HighlightedPreview({ text, entities }) {
  if (!entities?.length) return <span className="dim">No identifiers detected yet.</span>;
  const sorted = [...entities].sort((a, b) => a.start - b.start || b.end - a.end);
  const spans = [];
  let cur = -1;
  for (const e of sorted) if (e.start >= cur) { spans.push(e); cur = e.end; }
  const out = [];
  let pos = 0;
  spans.forEach((e, i) => {
    if (e.start > pos) out.push(<span key={`t${i}`}>{text.slice(pos, e.start)}</span>);
    out.push(
      <mark key={`e${i}`} className="hl" title={`${e.type} ${e.extractor}`}>
        {text.slice(e.start, e.end)}
      </mark>
    );
    pos = e.end;
  });
  if (pos < text.length) out.push(<span key="tail">{text.slice(pos)}</span>);
  return <span style={{ fontSize: 12, lineHeight: 1.7 }}>{out}</span>;
}
