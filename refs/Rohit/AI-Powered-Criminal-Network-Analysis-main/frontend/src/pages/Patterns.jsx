import React from "react";
import { api } from "../lib/api";
import {
  Bar, Card, Chip, ErrorBox, Loading, PageHead, Stat, Tabs, fmtInr, fmtNum, useApi,
} from "../components/ui";

/** Suspicious pattern findings, grouped by detector family. */
export default function Patterns({ onNavigate }) {
  const { data, error, loading, refresh } = useApi(() => api.patterns("?limit=400"));
  const [tab, setTab] = React.useState("all");
  const [expanded, setExpanded] = React.useState(null);

  if (loading) return <Loading label="Running typology detectors…" />;
  if (error) return <ErrorBox error={error} onRetry={refresh} />;

  const all = data?.patterns || [];
  const groups = {
    all: all,
    financial: all.filter((p) => FINANCIAL.includes(p.pattern_type)),
    communication: all.filter((p) => COMMS.includes(p.pattern_type)),
    anomaly: all.filter((p) => p.pattern_type === "behavioural_anomaly"),
  };
  const rows = groups[tab] || all;

  const bySeverity = all.reduce((acc, p) => {
    acc[p.severity] = (acc[p.severity] || 0) + 1;
    return acc;
  }, {});

  return (
    <>
      <PageHead
        title="Suspicious Pattern Detection"
        desc="Every finding is mapped to a recognised typology (FATF / FIU-IND for financial patterns, behavioural signatures for communications) rather than an opaque model output, so it can be defended in an investigative report."
        actions={<button className="btn" onClick={refresh}>Refresh</button>}
      />

      <div className="grid grid-4" style={{ marginBottom: 12 }}>
        <Stat label="Total findings" value={fmtNum(all.length)} />
        <Stat label="Critical" value={fmtNum(bySeverity.critical || 0)} accent="var(--critical)" />
        <Stat label="High" value={fmtNum(bySeverity.high || 0)} accent="var(--high)" />
        <Stat label="Medium" value={fmtNum(bySeverity.medium || 0)} accent="var(--medium)" />
      </div>

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "all", label: "All findings", count: groups.all.length },
          { id: "financial", label: "Money laundering", count: groups.financial.length },
          { id: "communication", label: "Communication", count: groups.communication.length },
          { id: "anomaly", label: "Behavioural anomalies", count: groups.anomaly.length },
        ]}
      />

      <Card>
        <div className="tbl-wrap" style={{ maxHeight: "calc(100vh - 380px)" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 84 }}>Severity</th>
                <th style={{ width: 150 }}>Type</th>
                <th>Finding</th>
                <th style={{ width: 96 }}>Confidence</th>
                <th style={{ width: 62 }}>Actors</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <React.Fragment key={p.id}>
                  <tr className="clickable" onClick={() => setExpanded(expanded === p.id ? null : p.id)}>
                    <td>
                      <Chip kind={p.severity}>{p.severity}</Chip>
                    </td>
                    <td className="dim" style={{ fontSize: 11.5 }}>
                      {p.pattern_type.replace(/_/g, " ")}
                    </td>
                    <td className="wrap-text">
                      <div style={{ fontWeight: 500, marginBottom: 2 }}>{p.summary}</div>
                      <div className="dim" style={{ fontSize: 11 }}>{p.typology}</div>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        <span className="mono">{(p.confidence * 100).toFixed(0)}%</span>
                        <Bar value={p.confidence * 100} />
                      </div>
                    </td>
                    <td className="num mono">{p.members?.length || 0}</td>
                  </tr>
                  {expanded === p.id && (
                    <tr>
                      <td colSpan={5} style={{ background: "var(--bg-2)" }}>
                        <PatternDetail pattern={p} onNavigate={onNavigate} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function PatternDetail({ pattern, onNavigate }) {
  const d = pattern.detail || {};
  return (
    <div className="stack" style={{ padding: "8px 2px" }}>
      {d.recommendation && (
        <div className="evidence">
          <strong style={{ color: "var(--text)" }}>Investigative recommendation: </strong>
          {d.recommendation}
        </div>
      )}

      {d.hops && (
        <div>
          <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>
            Money trail ({d.depth} hops, {d.value_retention != null ? `${(d.value_retention * 100).toFixed(0)}% value retained` : ""})
          </div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Txn</th>
                <th>From</th>
                <th>To</th>
                <th className="num">Amount</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {d.hops.map((h, i) => (
                <tr key={i}>
                  <td className="mono dim">{h.txn_id}</td>
                  <td>
                    {h.from_name}
                    <div className="dim mono" style={{ fontSize: 10 }}>{h.from}</div>
                  </td>
                  <td>
                    {h.to_name}
                    <div className="dim mono" style={{ fontSize: 10 }}>{h.to}</div>
                  </td>
                  <td className="num mono">{fmtInr(h.amount)}</td>
                  <td className="dim mono" style={{ fontSize: 11 }}>{String(h.date).slice(0, 16)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {d.amounts && (
        <div>
          <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>
            Transfers sized below the ₹10,00,000 CTR reporting threshold
          </div>
          <div className="row">
            {d.amounts.map((a, i) => (
              <span key={i} className="chip chip-high">{fmtInr(a)}</span>
            ))}
          </div>
        </div>
      )}

      {d.cycle && (
        <div className="evidence">
          <strong style={{ color: "var(--text)" }}>Circular route: </strong>
          <span className="mono">{d.cycle.join(" → ")}</span>
          <div style={{ marginTop: 3 }}>Total moved: {fmtInr(d.total_moved)}</div>
        </div>
      )}

      {d.deviations && (
        <div>
          <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>
            Robust z-scores vs corpus median
          </div>
          {Object.entries(d.deviations).map(([feature, z]) => (
            <div className="factor-row" key={feature}>
              <span className="dim">{feature.replace(/_/g, " ")}</span>
              <Bar value={Math.min(Math.abs(z) * 10, 100)} />
              <span className="num mono">{z > 0 ? "+" : ""}{z}σ</span>
            </div>
          ))}
        </div>
      )}

      {d.spokes && (
        <div className="evidence">
          <strong style={{ color: "var(--text)" }}>Hub: </strong>
          <span className="mono">{d.hub}</span> contacts {d.spoke_count} peers with
          inter-peer density {(d.inter_peer_density * 100).toFixed(0)}% — compartmentalised control.
        </div>
      )}

      {d.participants && (
        <div className="evidence">
          <strong style={{ color: "var(--text)" }}>Linked case: </strong>
          <code className="inline">{d.fir_id}</code> · {d.calls_in_window} calls at{" "}
          {d.rate_per_day}/day against a {d.baseline_per_day}/day baseline.
        </div>
      )}

      {pattern.member_names?.length > 0 && (
        <div>
          <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>Implicated entities</div>
          <div className="row">
            {pattern.members.map((id, i) => (
              <button
                key={id}
                className="btn btn-sm"
                onClick={() => /^[A-Z]{3}-\d{5}$/.test(id) && onNavigate("entity", id)}
              >
                {pattern.member_names[i] || id}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const FINANCIAL = ["structuring", "layering", "fan_out", "fan_in", "circular_flow", "rapid_passthrough", "dormant_burst"];
const COMMS = ["hub_and_spoke", "odd_hour_activity", "pre_incident_burst", "co_location", "one_way_traffic"];
