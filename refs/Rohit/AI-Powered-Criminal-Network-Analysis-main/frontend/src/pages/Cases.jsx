import React from "react";
import { api, getUser } from "../lib/api";
import {
  Card, Chip, ErrorBox, Loading, PageHead, Stat, fmtNum, useApi,
} from "../components/ui";

/** Case register and full FIR record view with NLP-highlighted narrative. */
export default function Cases({ caseId, onNavigate }) {
  if (caseId) return <CaseDetail firId={caseId} onNavigate={onNavigate} />;
  return <CaseList onNavigate={onNavigate} />;
}

function CaseList({ onNavigate }) {
  const [state, setState] = React.useState("");
  const [crimeType, setCrimeType] = React.useState("");
  const { data, error, loading } = useApi(() => api.cases("?limit=400"));

  if (loading) return <Loading label="Loading case register…" />;
  if (error) return <ErrorBox error={error} />;

  const all = data?.cases || [];
  const states = [...new Set(all.map((c) => c.state).filter(Boolean))].sort();
  const types = [...new Set(all.map((c) => c.crime_type).filter(Boolean))].sort();
  const rows = all.filter(
    (c) => (!state || c.state === state) && (!crimeType || c.crime_type === crimeType)
  );

  return (
    <>
      <PageHead
        title="Case Register"
        desc="All ingested FIRs with legal section classification, gravity assessment and Women Safety mandate flagging."
        actions={
          <button className="btn btn-primary" onClick={() => onNavigate("live")}>
            + Add Live Case
          </button>
        }
      />

      <div className="grid grid-4" style={{ marginBottom: 12 }}>
        <Stat label="Total cases" value={fmtNum(all.length)} />
        <Stat label="Women Safety mandate" value={fmtNum(all.filter((c) => c.women_safety_mandate).length)} accent="var(--high)" />
        <Stat label="Grave (gravity ≥ 9)" value={fmtNum(all.filter((c) => c.max_gravity >= 9).length)} accent="var(--critical)" />
        <Stat label="Under investigation" value={fmtNum(all.filter((c) => c.status === "Under Investigation").length)} />
      </div>

      <Card
        title={`Showing ${rows.length} of ${all.length}`}
        actions={
          <div className="btn-row">
            <select className="input" style={{ width: 168 }} value={state} onChange={(e) => setState(e.target.value)}>
              <option value="">All states</option>
              {states.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <select className="input" style={{ width: 190 }} value={crimeType} onChange={(e) => setCrimeType(e.target.value)}>
              <option value="">All crime types</option>
              {types.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        }
      >
        <div className="tbl-wrap" style={{ maxHeight: "calc(100vh - 400px)" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>FIR</th>
                <th>Crime type</th>
                <th>Sections</th>
                <th>Jurisdiction</th>
                <th>Priority</th>
                <th>Status</th>
                <th className="num">Gravity</th>
                <th>Filed</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.fir_id} className="clickable" onClick={() => onNavigate("case", c.fir_id)}>
                  <td className="mono" style={{ color: "var(--accent)" }}>{c.fir_id}</td>
                  <td>
                    {c.crime_type}
                    {c.women_safety_mandate && (
                      <div style={{ marginTop: 2 }}>
                        <Chip kind="high">Women Safety</Chip>
                      </div>
                    )}
                  </td>
                  <td className="mono dim" style={{ fontSize: 11 }}>{(c.ipc_sections || []).join(", ")}</td>
                  <td className="dim">{c.district}, {c.state}</td>
                  <td>
                    <Chip kind={String(c.priority).toLowerCase()}>{c.priority}</Chip>
                  </td>
                  <td style={{ fontSize: 11.5 }}>{c.status}</td>
                  <td className="num mono">{c.max_gravity}/10</td>
                  <td className="mono dim">{c.date_filed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function CaseDetail({ firId, onNavigate }) {
  const { data, error, loading, refresh } = useApi(() => api.caseDetail(firId), [firId]);
  const [extraction, setExtraction] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const user = getUser();
  const isAdmin = user?.role === "admin";
  const [editing, setEditing] = React.useState(false);
  const [editBusy, setEditBusy] = React.useState(false);
  const [editError, setEditError] = React.useState(null);
  const [editResult, setEditResult] = React.useState(null);
  const [history, setHistory] = React.useState(null);
  // form state derived from data.raw when entering edit mode
  const [form, setForm] = React.useState(null);

  React.useEffect(() => {
    if (!data?.description) return;
    let alive = true;
    setBusy(true);
    api
      .extract(data.description)
      .then((r) => alive && setExtraction(r))
      .catch(() => {})
      .finally(() => alive && setBusy(false));
    return () => {
      alive = false;
    };
  }, [data?.description]);

  React.useEffect(() => {
    if (!editing || !firId) return;
    // lazy load history for admin edit view
    api.caseHistory(firId).then(setHistory).catch(() => {});
  }, [editing, firId]);

  const startEdit = React.useCallback(() => {
    if (!data) return;
    const raw = data.raw || {};
    const src = (raw.accused && raw.accused.length ? raw.accused : (data.linked_entities || []).filter(e=>e.role==="accused").map(e=>({name:e.name, phone:"", alias:"", vehicle:"", age:""})));
    const rows = (src.length ? src : [{name:"",phone:"",alias:"",vehicle:"",age:""}]).map(a=>({
      name: a.name || "", phone: a.phone || "", alias: a.alias || "", vehicle: a.vehicle || "", age: a.age ? String(a.age) : ""
    }));
    setForm({
      fir_id: data.fir_id || "",
      station: data.station || raw.station || "",
      district: data.district || raw.district || "",
      state: data.state || raw.state || "",
      date_filed: (data.date_filed || raw.date_filed || "").slice(0, 10),
      ipc_sections: (data.ipc_sections || raw.ipc_sections || []).join(", "),
      crime_type: data.crime_type || raw.crime_type || "",
      priority: data.priority || raw.priority || "Medium",
      status: data.status || raw.status || "Under Investigation",
      officer: data.officer || raw.investigating_officer || raw.officer || "",
      description: data.description || raw.description || "",
      accusedRows: rows,
    });
    setEditError(null);
    setEditResult(null);
    setEditing(true);
  }, [data]);

  const submitEdit = async () => {
    if (!form) return;
    setEditBusy(true);
    setEditError(null);
    try {
      const accused = form.accusedRows.filter(r=>r.name.trim()).map(r=>({
        name: r.name.trim(),
        phone: r.phone.trim() || undefined,
        alias: r.alias.trim() || undefined,
        vehicle: r.vehicle.trim() || undefined,
        age: r.age ? Number(r.age) : undefined,
        gender: "Male",
      }));
      const payload = {
        fir_id: form.fir_id.trim(),
        station: form.station,
        district: form.district,
        state: form.state,
        date_filed: form.date_filed,
        ipc_sections: form.ipc_sections.split(",").map(s=>s.trim()).filter(Boolean),
        crime_type: form.crime_type,
        priority: form.priority,
        status: form.status,
        investigating_officer: form.officer,
        description: form.description,
        accused,
        locations_mentioned: [form.district, form.station].filter(Boolean),
        vehicles_involved: form.accusedRows.map(r=>r.vehicle).filter(Boolean),
      };
      const res = await api.updateCase(firId, payload);
      setEditResult(res);
      refresh();
      // if fir_id renamed, navigate to new id
      if (res.fir_id && res.fir_id !== firId) {
        onNavigate("case", res.fir_id);
      }
    } catch (e) {
      setEditError(e);
    } finally {
      setEditBusy(false);
    }
  };

  if (loading) return <Loading label="Loading case record…" />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  if (editing && form) {
    return (
      <>
        <PageHead
          title={`Edit ${data.fir_id}`}
          desc={`Admin edit — all fields including FIR ID are editable. Version ${data.version || 1} → ${ (data.version||1)+1 }`}
          actions={
            <div className="row">
              <button className="btn" onClick={() => setEditing(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={submitEdit} disabled={editBusy}>{editBusy ? "Saving & Recomputing…" : "Save Changes"}</button>
            </div>
          }
        />
        <div className="stack">
          <Card title="FIR Details — Editable (all fields)" note="Admin only. FIR ID may be renamed (must stay unique).">
            <div className="grid" style={{gridTemplateColumns:"1fr 1fr", gap:10}}>
              <label className="field"><span>FIR ID *</span><input className="input" value={form.fir_id} onChange={e=>setForm({...form, fir_id:e.target.value})} /></label>
              <label className="field"><span>Date Filed</span><input className="input" type="date" value={form.date_filed} onChange={e=>setForm({...form, date_filed:e.target.value})} /></label>
              <label className="field"><span>Station</span><input className="input" value={form.station} onChange={e=>setForm({...form, station:e.target.value})} /></label>
              <label className="field"><span>District</span><input className="input" value={form.district} onChange={e=>setForm({...form, district:e.target.value})} /></label>
              <label className="field"><span>State</span><input className="input" value={form.state} onChange={e=>setForm({...form, state:e.target.value})} /></label>
              <label className="field"><span>IPC Sections (comma)</span><input className="input" value={form.ipc_sections} onChange={e=>setForm({...form, ipc_sections:e.target.value})} /></label>
              <label className="field"><span>Crime Type</span><input className="input" value={form.crime_type} onChange={e=>setForm({...form, crime_type:e.target.value})} /></label>
              <label className="field"><span>Priority</span><select className="input" value={form.priority} onChange={e=>setForm({...form, priority:e.target.value})}><option>Low</option><option>Medium</option><option>High</option><option>Critical</option></select></label>
              <label className="field"><span>Status</span><select className="input" value={form.status} onChange={e=>setForm({...form, status:e.target.value})}><option>Under Investigation</option><option>Chargesheet Filed</option><option>Closed</option><option>Pending Trial</option></select></label>
              <label className="field"><span>Investigating Officer</span><input className="input" value={form.officer} onChange={e=>setForm({...form, officer:e.target.value})} /></label>
            </div>
          </Card>
          <Card title="Accused — Editable" actions={<button className="btn btn-sm" onClick={()=>setForm({...form, accusedRows:[...form.accusedRows, {name:"",phone:"",alias:"",vehicle:"",age:""}]})}>+ Add row</button>}>
            {form.accusedRows.map((row,i)=>(
              <div key={i} className="grid" style={{gridTemplateColumns:"1.2fr 1fr 0.8fr 1fr 0.5fr auto", gap:6, marginBottom:6}}>
                <input className="input" placeholder="Name *" value={row.name} onChange={e=>setForm({...form, accusedRows: form.accusedRows.map((x,j)=> j===i ? {...x, name:e.target.value}:x)})} />
                <input className="input" placeholder="Phone" value={row.phone} onChange={e=>setForm({...form, accusedRows: form.accusedRows.map((x,j)=> j===i ? {...x, phone:e.target.value}:x)})} />
                <input className="input" placeholder="Alias" value={row.alias} onChange={e=>setForm({...form, accusedRows: form.accusedRows.map((x,j)=> j===i ? {...x, alias:e.target.value}:x)})} />
                <input className="input" placeholder="Vehicle" value={row.vehicle} onChange={e=>setForm({...form, accusedRows: form.accusedRows.map((x,j)=> j===i ? {...x, vehicle:e.target.value}:x)})} />
                <input className="input" placeholder="Age" value={row.age} onChange={e=>setForm({...form, accusedRows: form.accusedRows.map((x,j)=> j===i ? {...x, age:e.target.value}:x)})} />
                <button className="btn btn-sm" onClick={()=>setForm({...form, accusedRows: form.accusedRows.filter((_,j)=>j!==i)})} disabled={form.accusedRows.length===1}>×</button>
              </div>
            ))}
          </Card>
          <Card title="Narrative — Editable">
            <textarea className="input" style={{minHeight:140}} value={form.description} onChange={e=>setForm({...form, description:e.target.value})} />
          </Card>
          {editError && <ErrorBox error={editError} />}
          {editResult && <Card title="Updated" note={`FIR ${editResult.fir_id} version ${editResult.version} saved. Graph/risk/search recomputed.`}><div className="row" style={{gap:6}}><button className="btn btn-sm" onClick={()=>onNavigate("case", editResult.fir_id)}>View Updated FIR</button><button className="btn btn-sm" onClick={()=>onNavigate("cases")}>Back to Register</button></div></Card>}
          {history?.history?.length >0 && <Card title="Version history" note={`${history.history.length} previous version(s) kept`}><div className="tbl-wrap"><table className="tbl"><thead><tr><th>Ver</th><th>Edited by</th><th>At</th><th>Snapshot FIR</th></tr></thead><tbody>{history.history.map(h=><tr key={h.version}><td className="mono">{h.version}</td><td>{h.edited_by}</td><td className="dim mono" style={{fontSize:11}}>{String(h.edited_at).slice(0,19).replace("T"," ")}</td><td className="mono" style={{fontSize:11}}>{h.snapshot?.fir_id || h.fir_id}</td></tr>)}</tbody></table></div></Card>}
        </div>
      </>
    );
  }

  return (
    <>
      <PageHead
        title={data.fir_id}
        desc={`${data.station} · ${data.district}, ${data.state} · filed ${data.date_filed} · IO: ${data.officer || "—"}${data.version ? ` · v${data.version}` : ""}${data.updated_at ? ` · updated ${String(data.updated_at).slice(0,19).replace("T"," ")}` : ""}`}
        actions={
          <div className="row">
            <button className="btn" onClick={() => onNavigate("cases")}>
              Back to register
            </button>
            {isAdmin && <button className="btn btn-primary" onClick={startEdit}>Edit</button>}
          </div>
        }
      />

      <div className="grid grid-2">
        <div className="stack">
          <Card title="Case narrative" note={busy ? "Extracting entities…" : "Extracted identifiers are highlighted; hover to see the entity type."}>
            <div className="narrative">
              <HighlightedText text={data.description || ""} entities={extraction?.entities || []} />
            </div>
          </Card>

          <Card title="AI summary" note="Extractive summary ranked by density of investigative signal.">
            <div className="narrative">{data.summary || "—"}</div>
          </Card>

          <Card title="Charged sections" note="Mapped to crime domain, gravity and BNS-2023 equivalents.">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Section</th>
                  <th>Offence</th>
                  <th>Domain</th>
                  <th className="num">Gravity</th>
                  <th>BNS</th>
                </tr>
              </thead>
              <tbody>
                {(data.section_detail || []).map((s) => (
                  <tr key={s.section}>
                    <td className="mono">{s.section}</td>
                    <td>
                      {s.description}
                      {s.women_safety && (
                        <div style={{ marginTop: 2 }}>
                          <Chip kind="high">Women Safety mandate</Chip>
                        </div>
                      )}
                    </td>
                    <td className="dim">{s.domain}</td>
                    <td className="num mono">{s.gravity}/10</td>
                    <td className="mono dim">{s.bns_equivalent || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>

        <div className="stack">
          <Card title="Linked entities" note="Resolved across all ingested sources, ranked by risk.">
            <div className="tbl-wrap" style={{ maxHeight: 320 }}>
              <table className="tbl">
                <tbody>
                  {(data.linked_entities || []).map((en) => (
                    <tr
                      key={`${en.entity_id}-${en.role}`}
                      className={["Person","BankAccount","Phone","Vehicle"].includes(en.type) ? "clickable" : ""}
                      onClick={() => ["Person","BankAccount","Phone","Vehicle"].includes(en.type) && onNavigate("entity", en.entity_id)}
                    >
                      <td>
                        <div style={{ color: ["Person","BankAccount","Phone","Vehicle"].includes(en.type) ? "var(--accent)" : undefined }}>{en.name}</div>
                        <div className="dim" style={{ fontSize: 10.5 }}>{en.type} · {en.role}</div>
                      </td>
                      <td className="num mono">{Number(en.risk_score || 0).toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {extraction && (
            <Card title="Extracted identifiers" note={`${extraction.entities.length} mentions across ${Object.keys(extraction.counts).length} types.`}>
              {Object.entries(extraction.counts).map(([type, count]) => (
                <div key={type} style={{ marginBottom: 7 }}>
                  <div className="row" style={{ gap: 6, marginBottom: 3 }}>
                    <strong style={{ fontSize: 12 }}>{type}</strong>
                    <span className="dim mono" style={{ fontSize: 11 }}>{count}</span>
                  </div>
                  <div className="row" style={{ gap: 4 }}>
                    {[...new Set(extraction.entities.filter((x) => x.type === type).map((x) => x.value))]
                      .slice(0, 10)
                      .map((v) => (
                        <span key={v} className="chip chip-neutral mono">{v}</span>
                      ))}
                  </div>
                </div>
              ))}
              {extraction.amounts?.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <strong style={{ fontSize: 12 }}>Monetary amounts</strong>
                  <div className="row" style={{ gap: 4, marginTop: 3 }}>
                    {extraction.amounts.map((a, i) => (
                      <span key={i} className="chip chip-high">₹{Number(a.amount_inr).toLocaleString("en-IN")}</span>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          )}

          {extraction?.roles && Object.keys(extraction.roles).length > 0 && (
            <Card title="Role cues detected in narrative" note="Command-language cues near each named person.">
              <table className="tbl">
                <tbody>
                  {Object.entries(extraction.roles).map(([name, role]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>
                        <Chip kind={role === "kingpin" ? "critical" : role === "lieutenant" ? "high" : "info"}>{role}</Chip>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

/** Renders text with extracted entity spans wrapped in highlight marks. */
function HighlightedText({ text, entities }) {
  if (!entities?.length) return <span>{text}</span>;

  // Resolve overlaps: keep the longest span at each position.
  const sorted = [...entities].sort((a, b) => a.start - b.start || b.end - a.end);
  const spans = [];
  let cursor = -1;
  for (const e of sorted) {
    if (e.start >= cursor) {
      spans.push(e);
      cursor = e.end;
    }
  }

  const out = [];
  let pos = 0;
  spans.forEach((e, i) => {
    if (e.start > pos) out.push(<span key={`t${i}`}>{text.slice(pos, e.start)}</span>);
    out.push(
      <mark className="hl" key={`e${i}`} title={`${e.type} · ${e.extractor} · ${(e.confidence * 100).toFixed(0)}%`}>
        {text.slice(e.start, e.end)}
      </mark>
    );
    pos = e.end;
  });
  if (pos < text.length) out.push(<span key="tail">{text.slice(pos)}</span>);
  return <>{out}</>;
}
