import React from "react";
import { api, getUser } from "../lib/api";
import {
  Bar, Card, Chip, ErrorBox, Loading, PageHead, Stat, fmtNum, useApi,
} from "../components/ui";

/* ======================================================================= */
export function Alerts({ onNavigate }) {
  const [severity, setSeverity] = React.useState("");
  const { data, error, loading, refresh } = useApi(() => api.alerts("?limit=300"));

  if (loading) return <Loading label="Loading alert worklist…" />;
  if (error) return <ErrorBox error={error} onRetry={refresh} />;

  const all = data?.alerts || [];
  const rows = severity ? all.filter((a) => a.severity === severity) : all;

  return (
    <>
      <PageHead
        title="Alert Worklist"
        desc="Prioritised by severity then confidence. Each alert carries the evidence that produced it — an alert an investigator cannot verify is one they will learn to ignore."
        actions={
          <div className="btn-row">
            <select className="input" style={{ width: 160 }} value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <option value="">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
            </select>
            <button className="btn" onClick={refresh}>Refresh</button>
          </div>
        }
      />

      <div className="grid grid-4" style={{ marginBottom: 12 }}>
        {Object.entries(data?.by_severity || {}).map(([sev, count]) => (
          <Stat key={sev} label={sev} value={fmtNum(count)} accent={`var(--${sev})`} />
        ))}
      </div>

      <div className="stack">
        {rows.map((a) => (
          <Card key={a.id}>
            <div className="row" style={{ gap: 8, marginBottom: 5 }}>
              <Chip kind={a.severity}>{a.severity}</Chip>
              <span className="chip chip-neutral">{a.alert_type.replace(/[:_]/g, " ")}</span>
              <strong style={{ fontSize: 13 }}>{a.title}</strong>
              <div style={{ flex: 1 }} />
              {a.entity_id && (
                <button className="btn btn-sm" onClick={() => onNavigate("entity", a.entity_id)}>
                  Open actor
                </button>
              )}
            </div>
            <div className="narrative">{a.description}</div>
            {a.evidence?.members?.length > 0 && (
              <div className="dim" style={{ fontSize: 11, marginTop: 5 }}>
                Implicated: <span className="mono">{a.evidence.members.slice(0, 6).join(", ")}</span>
              </div>
            )}
          </Card>
        ))}
      </div>
    </>
  );
}

/* ======================================================================= */
export function Search({ onNavigate }) {
  const [q, setQ] = React.useState("");
  const [submitted, setSubmitted] = React.useState("");
  const [result, setResult] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);

  async function run(e) {
    e?.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    setError(null);
    setSubmitted(q);
    try {
      setResult(await api.search(q));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHead
        title="Global Search"
        desc="BM25-ranked full-text search across entities, case narratives and pattern findings, with a Jaro-Winkler fuzzy fallback that tolerates transliteration variance in Indian names."
      />

      <Card style={{ marginBottom: 12 }}>
        <form onSubmit={run} className="row">
          <input
            className="input"
            style={{ flex: 1, minWidth: 260 }}
            placeholder="Search names, phone numbers, FIR IDs, accounts, vehicles, narratives…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !q.trim()}>
            {busy ? "Searching…" : "Search"}
          </button>
        </form>
        <div className="row" style={{ marginTop: 8, gap: 6 }}>
          <span className="dim" style={{ fontSize: 11 }}>Try:</span>
          {["trafficking", "Vikraam Desai", "layering", "9123456780", "Mumbai"].map((s) => (
            <button
              key={s}
              className="btn btn-sm"
              onClick={() => {
                setQ(s);
                setTimeout(() => document.querySelector("form button[type=submit]")?.click(), 0);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </Card>

      {error && <ErrorBox error={error} />}

      {result && (
        <Card
          title={`${result.total} results for “${submitted}”`}
          note={`${result.full_text_hits} full-text · ${result.fuzzy_hits} fuzzy · engine: ${result.engine}`}
        >
          {result.results.length === 0 ? (
            <div className="empty">No matches. Try a shorter or differently spelt query.</div>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Result</th>
                  <th style={{ width: 88 }}>Type</th>
                  <th>Context</th>
                  <th style={{ width: 92 }}>Match</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((r, i) => (
                  <tr
                    key={i}
                    className="clickable"
                    onClick={() => {
                      if (r.ref_type === "entity") onNavigate("entity", r.ref_id);
                      else if (r.ref_type === "case") onNavigate("case", r.ref_id);
                    }}
                  >
                    <td>
                      <div style={{ color: "var(--accent)", fontWeight: 500 }}>{r.title}</div>
                      <div className="dim mono" style={{ fontSize: 10.5 }}>{r.ref_id}</div>
                    </td>
                    <td>
                      <Chip kind="info">{r.meta?.type || r.ref_type}</Chip>
                    </td>
                    <td className="wrap-text dim" style={{ fontSize: 11.5 }}>{r.snippet}</td>
                    <td>
                      <div className="dim" style={{ fontSize: 10.5 }}>{r.match_type.replace(/_/g, " ")}</div>
                      <Bar value={Math.min(r.relevance * 100, 100)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}
    </>
  );
}

/* ======================================================================= */
export function AuditLedger() {
  const chain = useApi(() => api.auditChain(40));
  const verify = useApi(() => api.auditVerify());
  const stats = useApi(() => api.auditStats());
  const [demo, setDemo] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);
  const user = getUser();

  async function runTamperDemo() {
    setBusy(true);
    setError(null);
    try {
      setDemo(await api.tamperDemo(1));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
      verify.refresh();
    }
  }

  return (
    <>
      <PageHead
        title="Blockchain Audit Ledger"
        desc="Append-only SHA-256 hash chain recording who accessed which record. The defensible application of blockchain here is accountability, not case data storage — putting citizen records on a chain would be a privacy failure."
      />

      <div className="grid grid-4" style={{ marginBottom: 12 }}>
        <Stat label="Blocks" value={fmtNum(stats.data?.total_blocks)} />
        <Stat
          label="Chain integrity"
          value={verify.data?.valid ? "VERIFIED" : verify.data ? "BROKEN" : "…"}
          accent={verify.data?.valid ? "var(--low)" : "var(--critical)"}
          sub={verify.data?.valid ? "no entry altered or removed" : verify.data?.reason}
        />
        <Stat label="Algorithm" value="SHA-256" sub="per-block Merkle commitment" />
        <Stat label="Head height" value={fmtNum(stats.data?.head_height)} />
      </div>

      <Card
        title="Tamper detection demonstration"
        note="Modifies one audit block, verifies the chain, then restores the original value — so the integrity guarantee is demonstrable rather than asserted. Requires the admin role."
        style={{ marginBottom: 12 }}
        actions={
          <button className="btn btn-danger" onClick={runTamperDemo} disabled={busy || user?.role !== "admin"}>
            {busy ? "Running…" : "Run demonstration"}
          </button>
        }
      >
        {user?.role !== "admin" && (
          <div className="dim" style={{ fontSize: 12 }}>
            Sign in as <code className="inline">admin</code> to run this demonstration.
          </div>
        )}
        {error && <ErrorBox error={error} />}
        {demo && (
          <div className="stack">
            <div className="grid grid-3">
              <Stat label="Before tampering" value={demo.before_tampering.valid ? "VALID" : "BROKEN"} accent="var(--low)" />
              <Stat
                label="After tampering"
                value={demo.after_tampering.valid ? "VALID" : "DETECTED"}
                accent="var(--critical)"
                sub={`failed at block ${demo.after_tampering.failed_at}`}
              />
              <Stat label="After restoration" value={demo.after_restoration.valid ? "VALID" : "BROKEN"} accent="var(--low)" />
            </div>
            <div className="evidence">{demo.conclusion}</div>
            {demo.after_tampering.recorded_hash && (
              <div>
                <div className="dim" style={{ fontSize: 11 }}>Recorded hash</div>
                <div className="hash">{demo.after_tampering.recorded_hash}</div>
                <div className="dim" style={{ fontSize: 11, marginTop: 5 }}>Recomputed from tampered content</div>
                <div className="hash" style={{ color: "var(--critical)" }}>{demo.after_tampering.computed_hash}</div>
              </div>
            )}
          </div>
        )}
      </Card>

      <Card title="Ledger entries" note="Most recent first. Each block commits to the previous block's digest.">
        {chain.loading ? (
          <Loading />
        ) : (
          <div className="tbl-wrap" style={{ maxHeight: 460 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: 46 }}>#</th>
                  <th style={{ width: 150 }}>Timestamp</th>
                  <th style={{ width: 108 }}>Actor</th>
                  <th style={{ width: 168 }}>Action</th>
                  <th>Resource</th>
                  <th>Hash</th>
                </tr>
              </thead>
              <tbody>
                {(chain.data?.entries || []).map((b) => (
                  <tr key={b.idx}>
                    <td className="mono dim">{b.idx}</td>
                    <td className="mono dim" style={{ fontSize: 10.5 }}>{b.ts.slice(0, 19).replace("T", " ")}</td>
                    <td className="mono">{b.actor}</td>
                    <td>
                      <span className="chip chip-neutral">{b.action}</span>
                    </td>
                    <td className="mono dim" style={{ fontSize: 11 }}>{b.resource || "—"}</td>
                    <td className="hash">{b.hash.slice(0, 22)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

/* ======================================================================= */
export function Evaluation() {
  const { data, error, loading, refresh } = useApi(() => api.evaluation());

  if (loading) return <Loading label="Evaluating against ground truth…" />;
  if (error) return <ErrorBox error={error} onRetry={refresh} />;
  if (!data?.available) return <Card note={data?.message} />;

  const baselines = Object.entries(data.baselines || {});
  const maxMap = Math.max(
    data.model.mean_average_precision,
    ...baselines.map(([, b]) => b.mean_average_precision)
  );

  return (
    <>
      <PageHead
        title="Model Evaluation"
        desc="Most systems claim they find the kingpin; this one is measured. The corpus generator plants a known hierarchy that the analytics pipeline never sees, so detection accuracy is falsifiable rather than asserted."
      />

      <div className="grid grid-4" style={{ marginBottom: 12 }}>
        <Stat label="Labelled actors" value={fmtNum(data.corpus.labelled_actors)} sub={`${data.corpus.networks} networks`} />
        <Stat label="Kingpin in top 3" value={`${(data.network_recovery.top_3_hit_rate * 100).toFixed(0)}%`} accent="var(--low)" sub={`${data.network_recovery.kingpin_in_top_3}/${data.network_recovery.networks_evaluated} networks`} />
        <Stat label="Correct at rank 1" value={`${(data.network_recovery.rank_1_hit_rate * 100).toFixed(0)}%`} accent="var(--accent)" />
        <Stat
          label="vs best baseline"
          value={`+${data.comparison.relative_improvement_pct ?? 0}%`}
          accent="var(--low)"
          sub={`MAP ${data.model.mean_average_precision} vs ${data.comparison.best_baseline_map}`}
        />
      </div>

      <div className="grid grid-2" style={{ marginBottom: 12 }}>
        <Card title="Baseline comparison" note="Mean Average Precision for kingpin identification. Higher is better.">
          <div className="factor-row" style={{ borderBottom: "1px solid var(--border)", paddingBottom: 7 }}>
            <strong>Composite score (ours)</strong>
            <Bar value={data.model.mean_average_precision} max={maxMap} color="var(--low)" />
            <span className="num mono" style={{ color: "var(--low)" }}>
              {data.model.mean_average_precision.toFixed(3)}
            </span>
          </div>
          {baselines
            .sort((a, b) => b[1].mean_average_precision - a[1].mean_average_precision)
            .map(([name, b]) => (
              <div className="factor-row" key={name}>
                <span className="dim">{name.replace(/_/g, " ")}</span>
                <Bar value={b.mean_average_precision} max={maxMap} color="var(--text-3)" />
                <span className="num mono dim">{b.mean_average_precision.toFixed(3)}</span>
              </div>
            ))}
          <div className="evidence" style={{ marginTop: 10 }}>{data.comparison.interpretation}</div>
        </Card>

        <Card title="Score separation by true role" note="A working detector must stratify the hierarchy, not just rank one actor correctly.">
          <table className="tbl">
            <thead>
              <tr>
                <th>True role</th>
                <th className="num">Count</th>
                <th style={{ width: 130 }}>Mean influence score</th>
                <th className="num">Range</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.role_score_separation).map(([role, s]) => (
                <tr key={role}>
                  <td>
                    <Chip kind={role === "kingpin" ? "critical" : role === "lieutenant" ? "high" : "neutral"}>{role}</Chip>
                  </td>
                  <td className="num mono">{s.count}</td>
                  <td>
                    <div className="row" style={{ gap: 6 }}>
                      <span className="mono">{s.mean_kingpin_score}</span>
                      <Bar value={s.mean_kingpin_score} />
                    </div>
                  </td>
                  <td className="num mono dim">{s.min}–{s.max}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Card title="Per-network recovery" note="Was the planted kingpin recovered within their own network?" style={{ marginBottom: 12 }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Network</th>
              <th className="num">Actors</th>
              <th>Planted kingpin</th>
              <th className="num">Predicted rank</th>
              <th className="num">Score</th>
              <th>Tier assigned</th>
              <th>Recovered</th>
            </tr>
          </thead>
          <tbody>
            {data.per_network.map((n) => (
              <tr key={n.network}>
                <td>{n.network}</td>
                <td className="num mono">{n.actors_in_network}</td>
                <td>{n.true_kingpin}</td>
                <td className="num mono">#{n.predicted_rank_within_network}</td>
                <td className="num mono">{n.kingpin_score?.toFixed(1)}</td>
                <td className="dim" style={{ fontSize: 11.5 }}>{n.tier_assigned}</td>
                <td>
                  {n.identified_at_rank_1 ? (
                    <Chip kind="low">Rank 1</Chip>
                  ) : n.identified_in_top_3 ? (
                    <Chip kind="medium">Top 3</Chip>
                  ) : (
                    <Chip kind="high">Missed</Chip>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Methodology" note="Why this evaluation is meaningful.">
        <div className="narrative">{data.methodology}</div>
        <div className="grid grid-3" style={{ marginTop: 11 }}>
          {Object.entries(data.model.precision_at_k).map(([k, v]) => (
            <Stat key={k} label={`Precision ${k}`} value={v.toFixed(3)} />
          ))}
          <Stat label="Mean reciprocal rank" value={data.model.mrr.toFixed(3)} />
          <Stat label="Command-tier precision" value={data.model.command_tier_precision.toFixed(3)} />
          <Stat label="Command-tier recall" value={data.model.command_tier_recall.toFixed(3)} />
        </div>
      </Card>
    </>
  );
}

/* ======================================================================= */
export function LinkPrediction({ onNavigate }) {
  const { data, error, loading, refresh } = useApi(() => api.predictLinks(30));

  if (loading) return <Loading label="Predicting unobserved relationships…" />;
  if (error) return <ErrorBox error={error} onRetry={refresh} />;

  return (
    <>
      <PageHead
        title="Hidden Connection Discovery"
        desc="Predicted relationships that are not recorded in any source document. Each prediction lists the shared associates that justify it, so an investigator can verify rather than trust it."
      />

      <Card title={`${data?.total ?? 0} candidate links`} note={data?.method}>
        <div className="tbl-wrap" style={{ maxHeight: "calc(100vh - 320px)" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Actor A</th>
                <th>Actor B</th>
                <th style={{ width: 130 }}>Probability</th>
                <th className="num">Shared</th>
                <th>Basis</th>
              </tr>
            </thead>
            <tbody>
              {(data?.predictions || []).map((p, i) => (
                <tr key={i}>
                  <td className="clickable" style={{ color: "var(--accent)" }} onClick={() => onNavigate("entity", p.source)}>
                    {p.source_name}
                  </td>
                  <td className="clickable" style={{ color: "var(--accent)" }} onClick={() => onNavigate("entity", p.target)}>
                    {p.target_name}
                  </td>
                  <td>
                    <div className="row" style={{ gap: 6 }}>
                      <span className="mono">{(p.probability * 100).toFixed(0)}%</span>
                      <Bar value={p.probability * 100} />
                      <Chip kind={p.confidence_band === "high" ? "critical" : p.confidence_band === "medium" ? "high" : "medium"}>
                        {p.confidence_band}
                      </Chip>
                    </div>
                  </td>
                  <td className="num mono">{p.shared_count}</td>
                  <td className="wrap-text dim" style={{ fontSize: 11.5 }}>{p.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

/* ======================================================================= */
export function Communities({ onNavigate }) {
  const { data, error, loading, refresh } = useApi(() => api.communities());

  if (loading) return <Loading label="Detecting criminal cells…" />;
  if (error) return <ErrorBox error={error} onRetry={refresh} />;

  const cells = (data?.communities || []).filter((c) => c.size >= 2);

  return (
    <>
      <PageHead
        title="Criminal Cell Detection"
        desc={`Louvain modularity partitioning of the association network. Modularity ${data?.modularity} across ${data?.count} detected groups — high insularity indicates a tight, compartmentalised cell rather than incidental co-mention.`}
      />

      <div className="grid grid-3">
        {cells.map((c) => (
          <Card key={c.community_id} title={`Cell-${String(c.community_id).padStart(2, "0")}`} note={`${c.size} actors · density ${c.density}`}>
            <div className="grid grid-2" style={{ marginBottom: 9 }}>
              <Stat label="Insularity" value={c.insularity.toFixed(2)} accent={c.insularity > 0.7 ? "var(--critical)" : undefined} />
              <Stat label="Avg risk" value={c.avg_risk.toFixed(0)} />
            </div>
            <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>
              {c.internal_edges} internal · {c.external_edges} external links
            </div>
            <div className="row" style={{ gap: 4 }}>
              {c.members.map((id, i) => (
                <button key={id} className="btn btn-sm" onClick={() => onNavigate("entity", id)}>
                  {c.member_names[i]}
                </button>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
