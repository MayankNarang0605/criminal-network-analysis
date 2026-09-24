import React from "react";
import { api } from "../lib/api";
import {
  Bar, Card, Chip, ErrorBox, Loading, PageHead, Stat, Tabs, fmtInr, fmtNum,
  tierColor, useApi,
} from "../components/ui";

/**
 * Entity dossier.
 *
 * Everything an investigator needs about one actor on a single page: identity
 * and aliases resolved across sources, explainable risk attribution, command
 * assessment, linked cases, the evidence behind every relationship, and pattern
 * hits. The evidence trail is the point — a claim without provenance is useless
 * in an investigation.
 */
export default function EntityDossier({ entityId, onNavigate }) {
  const [tab, setTab] = React.useState("overview");
  const { data, error, loading, refresh } = useApi(() => api.entity(entityId, 2), [entityId]);
  const risk = useApi(() => {
    const t = data?.entity?.type;
    if (t && t !== "Person") return Promise.resolve(null);
    return api.riskDetail(entityId).catch(() => null);
  }, [entityId, data?.entity?.type]);

  if (loading) return <Loading label="Assembling dossier…" />;
  if (error) return <ErrorBox error={error} onRetry={refresh} />;
  if (!data) return null;

  const e = data.entity;
  const k = data.kingpin_assessment;
  const m = data.graph_metrics || {};

  return (
    <>
      <PageHead
        title={e.name}
        desc={`${e.type} · ${e.entity_id}${e.aliases?.length ? ` · also recorded as: ${e.aliases.join(", ")}` : ""}`}
        actions={
          <div className="btn-row">
            <button className="btn" onClick={() => onNavigate("graph", e.entity_id)}>
              View in graph
            </button>
            <button className="btn" onClick={refresh}>Refresh</button>
          </div>
        }
      />

      <div className="grid grid-6" style={{ marginBottom: 12 }}>
        <Stat
          label="Risk score"
          value={Number(e.risk_score).toFixed(1)}
          sub={e.risk_band}
          accent={e.risk_score >= 70 ? "var(--critical)" : e.risk_score >= 50 ? "var(--high)" : undefined}
        />
        <Stat
          label="Influence score"
          value={k ? k.kingpin_score.toFixed(1) : "—"}
          sub={k?.tier}
          accent={k ? tierColor(k.tier) : undefined}
        />
        <Stat label="Associations" value={fmtNum(data.relationship_count)} sub={`degree ${m.degree ?? 0}`} />
        <Stat label="Linked cases" value={fmtNum(data.cases.length)} />
        <Stat label="Pattern hits" value={fmtNum(data.patterns.length)} accent={data.patterns.length ? "var(--high)" : undefined} />
        <Stat label="Detected cell" value={data.community?.label || "—"} sub={data.community ? `cohesion ${data.community.cohesion}` : undefined} />
      </div>

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "overview", label: "Assessment" },
          { id: "network", label: "Associations", count: data.relationships.length },
          { id: "cases", label: "Cases", count: data.cases.length },
          { id: "patterns", label: "Patterns", count: data.patterns.length },
        ]}
      />

      {tab === "overview" && (
        <div className="grid grid-2">
          <Card title="Risk attribution" note="Every factor is computed from source records and independently verifiable.">
            {risk.loading && <Loading label="Scoring…" />}
            {risk.data && (
              <>
                <div className="narrative" style={{ marginBottom: 11 }}>{risk.data.narrative}</div>
                {risk.data.factors.map((f) => (
                  <div key={f.factor} style={{ marginBottom: 9 }}>
                    <div className="factor-row">
                      <span>{f.label}</span>
                      <Bar value={f.points_contributed} max={f.max_points} />
                      <span className="num mono">
                        {f.points_contributed.toFixed(1)}
                        <span className="dim">/{f.max_points}</span>
                      </span>
                    </div>
                    <div className="dim" style={{ fontSize: 11.5, paddingLeft: 2 }}>
                      {f.explanation}
                    </div>
                  </div>
                ))}
              </>
            )}
          </Card>

          <div className="stack">
            {k && (
              <Card title="Command assessment" note="Why this actor is or is not leadership.">
                <div className="narrative" style={{ marginBottom: 10 }}>{k.explanation}</div>
                {Object.entries(k.contributions).map(([factor, pts]) => (
                  <div className="factor-row" key={factor}>
                    <span className="dim">{factor.replace(/_/g, " ")}</span>
                    <Bar value={pts} max={26} />
                    <span className="num mono">{pts.toFixed(1)}</span>
                  </div>
                ))}
                <dl className="kv" style={{ marginTop: 10 }}>
                  <dt>Insulation index</dt>
                  <dd className="mono">{k.insulation_index.toFixed(3)}</dd>
                  <dt>Damage if removed</dt>
                  <dd className="mono">{(k.network_damage_if_removed * 100).toFixed(1)}%</dd>
                  <dt>Articulation point</dt>
                  <dd>{m.is_articulation_point ? <Chip kind="critical">Yes — removal splits the network</Chip> : "No"}</dd>
                </dl>
              </Card>
            )}

            <Card title="Network position" note="Graph-theoretic measures on the person-only projection.">
              <dl className="kv">
                {[
                  ["Degree", m.degree],
                  ["Weighted strength", m.strength],
                  ["Betweenness", m.betweenness],
                  ["Closeness", m.closeness],
                  ["Eigenvector", m.eigenvector],
                  ["PageRank", m.pagerank],
                  ["Clustering coeff.", m.clustering],
                  ["k-core", m.k_core],
                ].map(([label, value]) => (
                  <React.Fragment key={label}>
                    <dt>{label}</dt>
                    <dd className="mono">{value != null ? Number(value).toFixed(4).replace(/\.?0+$/, "") : "—"}</dd>
                  </React.Fragment>
                ))}
              </dl>
            </Card>

            {Object.keys(e.attributes || {}).length > 0 && (
              <Card title="Recorded attributes" note="Merged across all source records during entity resolution.">
                <dl className="kv">
                  {Object.entries(e.attributes)
                    .filter(([, v]) => typeof v !== "object")
                    .map(([key, value]) => (
                      <React.Fragment key={key}>
                        <dt>{key.replace(/_/g, " ")}</dt>
                        <dd>{String(value)}</dd>
                      </React.Fragment>
                    ))}
                </dl>
                {e.attributes.inferred_roles?.length > 0 && (
                  <div className="row" style={{ marginTop: 8 }}>
                    <span className="dim" style={{ fontSize: 11 }}>NLP-inferred role cues:</span>
                    {e.attributes.inferred_roles.map((r) => (
                      <Chip key={r} kind="info">{r}</Chip>
                    ))}
                  </div>
                )}
              </Card>
            )}
          </div>
        </div>
      )}

      {tab === "network" && (
        <Card title="Associations with evidence" note="Each edge lists the source record and extraction basis that produced it.">
          <div className="tbl-wrap" style={{ maxHeight: "calc(100vh - 400px)" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Counterparty</th>
                  <th>Relationship</th>
                  <th className="num">Confidence</th>
                  <th className="num">Observations</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {data.relationships.map((r, i) => {
                  const isSource = r.source_id === e.entity_id;
                  const otherId = isSource ? r.target_id : r.source_id;
                  const otherName = isSource ? r.target_name : r.source_name;
                  const otherType = isSource ? r.target_type : r.source_type;
                  return (
                    <tr key={i}>
                      <td
                        className={["Person","BankAccount","Phone","Vehicle","Organization"].includes(otherType) ? "clickable" : ""}
                        onClick={() => ["Person","BankAccount","Phone","Vehicle","Organization"].includes(otherType) && onNavigate("entity", otherId)}
                      >
                        <div style={{ color: ["Person","BankAccount","Phone","Vehicle","Organization"].includes(otherType) ? "var(--accent)" : undefined }}>
                          {otherName}
                        </div>
                        <div className="dim" style={{ fontSize: 10.5 }}>{otherType}</div>
                      </td>
                      <td>
                        <span className="chip chip-neutral">{r.rel_type.replace(/_/g, " ").toLowerCase()}</span>
                      </td>
                      <td className="num mono">{(r.confidence * 100).toFixed(0)}%</td>
                      <td className="num mono">{r.observations}</td>
                      <td className="wrap-text">
                        {(r.evidence || []).slice(0, 2).map((ev, j) => (
                          <div className="evidence" key={j}>
                            <div className="mono dim" style={{ fontSize: 10.5, marginBottom: 2 }}>
                              {ev.source}
                              {ev.cue ? ` · cue: "${ev.cue}"` : ""}
                            </div>
                            {ev.sentence || ev.note ||
                              (ev.call_count ? `${ev.call_count} calls, ${ev.total_duration_sec}s total` : "") ||
                              (ev.total_amount_inr ? `${fmtInr(ev.total_amount_inr)} across ${ev.transaction_count} transactions` : "")}
                          </div>
                        ))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {tab === "cases" && (
        <Card title="Linked case records">
          <table className="tbl">
            <thead>
              <tr>
                <th>FIR</th>
                <th>Role</th>
                <th>Crime type</th>
                <th>Sections</th>
                <th>Jurisdiction</th>
                <th>Status</th>
                <th>Filed</th>
              </tr>
            </thead>
            <tbody>
              {data.cases.map((c) => (
                <tr key={c.fir_id} className="clickable" onClick={() => onNavigate("case", c.fir_id)}>
                  <td className="mono" style={{ color: "var(--accent)" }}>{c.fir_id}</td>
                  <td>
                    <Chip kind={c.role === "accused" ? "high" : "neutral"}>{c.role}</Chip>
                  </td>
                  <td>{c.crime_type}</td>
                  <td className="mono dim" style={{ fontSize: 11 }}>{(c.ipc_sections || []).join(", ")}</td>
                  <td className="dim">{c.district}, {c.state}</td>
                  <td>{c.status}</td>
                  <td className="mono dim">{c.date_filed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {tab === "patterns" && (
        <div className="stack">
          {data.patterns.length === 0 && <Card note="No suspicious patterns implicate this actor." />}
          {data.patterns.map((p) => (
            <Card key={p.id} title={p.typology} note={p.pattern_type.replace(/_/g, " ")}>
              <div className="row" style={{ gap: 7, marginBottom: 7 }}>
                <Chip kind={p.severity}>{p.severity}</Chip>
                <span className="dim mono">{(p.confidence * 100).toFixed(0)}% confidence</span>
              </div>
              <div className="narrative">{p.summary}</div>
              {p.detail?.recommendation && (
                <div className="evidence" style={{ marginTop: 8 }}>
                  <strong style={{ color: "var(--text)" }}>Recommendation: </strong>
                  {p.detail.recommendation}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
