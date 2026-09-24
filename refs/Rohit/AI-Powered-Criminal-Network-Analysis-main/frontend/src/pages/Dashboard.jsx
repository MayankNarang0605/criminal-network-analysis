import React from "react";
import { api } from "../lib/api";
import {
  Bar, Card, Chip, ErrorBox, Loading, PageHead, Stat, fmtInr, fmtNum,
  tierColor, useApi,
} from "../components/ui";
import {
  Area, AreaChart, Bar as RBar, BarChart, CartesianGrid, Cell, Legend, Pie,
  PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const AXIS = { stroke: "#6b7d99", fontSize: 10 };
const TIP = {
  contentStyle: {
    background: "#151d2e",
    border: "1px solid #2f3d5c",
    borderRadius: 6,
    fontSize: 12,
  },
  labelStyle: { color: "#9aabc4" },
};
const PIE_COLORS = ["#4a90ff", "#ff9436", "#4ad9a4", "#b57bff", "#ffd23f", "#ff7bd0", "#5ec8d8", "#e8734a"];

export default function Dashboard({ onNavigate }) {
  const { data, error, loading, refresh } = useApi(() => api.dashboard());

  if (loading) return <Loading label="Computing network intelligence…" />;
  if (error) return <ErrorBox error={error} onRetry={refresh} />;
  if (!data) return null;

  const c = data.counts;
  const crimeData = Object.entries(data.crime_distribution || {}).map(([name, value]) => ({ name, value }));
  const stateData = Object.entries(data.state_distribution || {})
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }));
  const patternData = Object.entries(data.pattern_summary || {})
    .map(([name, value]) => ({ name: name.replace(/_/g, " "), value }))
    .sort((a, b) => b.value - a.value);
  const timeline = (data.timeline || []).map((t) => ({ month: t.month, cases: t.cases }));

  return (
    <>
      <PageHead
        title="Operational Overview"
        desc="Consolidated intelligence picture across all ingested sources. Every figure below is derived from the ingested corpus and is traceable to source records."
        actions={
          <button className="btn" onClick={refresh}>
            Refresh
          </button>
        }
      />

      <div className="grid grid-6" style={{ marginBottom: 12 }}>
        <Stat label="Cases (FIRs)" value={fmtNum(c.cases)} sub={`${fmtNum(c.persons)} persons resolved`} />
        <Stat label="Entities" value={fmtNum(c.entities)} sub={`${fmtNum(c.relationships)} relationships`} />
        <Stat label="Networks detected" value={fmtNum(c.networks_detected)} sub="Louvain communities" accent="var(--accent)" />
        <Stat label="Suspicious patterns" value={fmtNum(c.patterns)} sub={`${fmtNum(data.severity_summary?.critical || 0)} critical`} accent="var(--high)" />
        <Stat label="Active alerts" value={fmtNum(c.alerts)} sub="Prioritised worklist" accent="var(--critical)" />
        <Stat
          label="Audit ledger"
          value={fmtNum(c.audit_blocks)}
          sub={data.audit?.valid ? "Integrity verified" : "COMPROMISED"}
          accent={data.audit?.valid ? "var(--low)" : "var(--critical)"}
        />
      </div>

      <div className="grid grid-2" style={{ marginBottom: 12 }}>
        <Card
          title="Command-tier actors"
          note="Composite Kingpin Influence Score — not degree centrality. Click to open the full assessment."
          actions={
            <button className="btn btn-sm" onClick={() => onNavigate("kingpins")}>
              Full ranking
            </button>
          }
        >
          <div className="tbl-wrap" style={{ maxHeight: 330 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Actor</th>
                  <th>Tier</th>
                  <th style={{ width: 120 }}>Score</th>
                  <th>Primary driver</th>
                </tr>
              </thead>
              <tbody>
                {(data.top_kingpins || []).map((k) => (
                  <tr
                    key={k.entity_id}
                    className="clickable"
                    onClick={() => onNavigate("entity", k.entity_id)}
                  >
                    <td className="dim mono">{k.rank}</td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{k.name}</div>
                      <div className="dim mono" style={{ fontSize: 10.5 }}>{k.entity_id}</div>
                    </td>
                    <td>
                      <span style={{ color: tierColor(k.tier), fontSize: 11.5, fontWeight: 600 }}>
                        {k.tier}
                      </span>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        <span className="mono">{k.kingpin_score.toFixed(1)}</span>
                        <Bar value={k.kingpin_score} />
                      </div>
                    </td>
                    <td className="dim" style={{ fontSize: 11.5 }}>
                      {(k.primary_drivers || []).slice(0, 2).join(", ").replace(/_/g, " ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card
          title="Priority alerts"
          note="Ranked by severity then confidence."
          actions={
            <button className="btn btn-sm" onClick={() => onNavigate("alerts")}>
              All alerts
            </button>
          }
        >
          <div className="scroll-y" style={{ maxHeight: 330 }}>
            {(data.alerts || []).map((a) => (
              <div
                key={a.id}
                style={{
                  padding: "8px 0",
                  borderBottom: "1px solid var(--bg-2)",
                  cursor: a.entity_id ? "pointer" : "default",
                }}
                onClick={() => a.entity_id && onNavigate("entity", a.entity_id)}
              >
                <div className="row" style={{ gap: 7, marginBottom: 3 }}>
                  <Chip kind={a.severity}>{a.severity}</Chip>
                  <span style={{ fontWeight: 600, fontSize: 12.5 }}>{a.title}</span>
                </div>
                <div className="dim" style={{ fontSize: 11.5, lineHeight: 1.5 }}>
                  {a.description}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 12 }}>
        <Card title="Financial exposure traced" note="Aggregated from the ingested transaction ledger.">
          <div className="grid grid-3" style={{ marginBottom: 10 }}>
            <Stat label="Total traced" value={fmtInr(data.financial.total_traced_inr)} />
            <Stat label="Flagged" value={fmtInr(data.financial.flagged_inr)} accent="var(--critical)" />
            <Stat label="Flagged share" value={`${data.financial.flagged_share_pct}%`} accent="var(--high)" />
          </div>
          <ResponsiveContainer width="100%" height={172}>
            <BarChart data={patternData.slice(0, 8)} layout="vertical" margin={{ left: 4, right: 12 }}>
              <CartesianGrid stroke="#24304a" horizontal={false} />
              <XAxis type="number" {...AXIS} />
              <YAxis type="category" dataKey="name" width={128} {...AXIS} />
              <Tooltip {...TIP} />
              <RBar dataKey="value" fill="#ff9436" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Highest risk individuals" note="Explainable composite score; open an actor to see factor attribution.">
          <div className="tbl-wrap" style={{ maxHeight: 288 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Individual</th>
                  <th>Band</th>
                  <th style={{ width: 130 }}>Risk</th>
                </tr>
              </thead>
              <tbody>
                {(data.top_risk || []).map((r) => (
                  <tr key={r.entity_id} className="clickable" onClick={() => onNavigate("entity", r.entity_id)}>
                    <td>{r.name}</td>
                    <td>
                      <Chip kind={r.risk_band}>{r.risk_band}</Chip>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        <span className="mono">{Number(r.risk_score).toFixed(1)}</span>
                        <Bar value={r.risk_score} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="grid grid-3">
        <Card title="Crime domain distribution">
          <ResponsiveContainer width="100%" height={210}>
            <PieChart>
              <Pie
                data={crimeData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={72}
                innerRadius={40}
                paddingAngle={2}
              >
                {crimeData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip {...TIP} />
              <Legend wrapperStyle={{ fontSize: 10.5 }} />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Case volume by state">
          <ResponsiveContainer width="100%" height={210}>
            <BarChart data={stateData} margin={{ left: -18, right: 8 }}>
              <CartesianGrid stroke="#24304a" vertical={false} />
              <XAxis dataKey="name" {...AXIS} angle={-28} textAnchor="end" height={54} interval={0} />
              <YAxis {...AXIS} />
              <Tooltip {...TIP} />
              <RBar dataKey="value" fill="#4a90ff" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Case registration timeline">
          <ResponsiveContainer width="100%" height={210}>
            <AreaChart data={timeline} margin={{ left: -18, right: 8 }}>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4ad9a4" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#4ad9a4" stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#24304a" vertical={false} />
              <XAxis dataKey="month" {...AXIS} angle={-28} textAnchor="end" height={54} interval={0} />
              <YAxis {...AXIS} />
              <Tooltip {...TIP} />
              <Area type="monotone" dataKey="cases" stroke="#4ad9a4" fill="url(#g1)" strokeWidth={1.6} />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card
        title="Women Safety Division mandate"
        note={`${data.women_safety?.cases_in_mandate ?? 0} of ${fmtNum(c.cases)} cases fall within the division's statutory mandate (${data.women_safety?.mandate_share_pct ?? 0}%).`}
        style={{ marginTop: 12 }}
        actions={
          <button className="btn btn-sm" onClick={() => onNavigate("women")}>
            Open module
          </button>
        }
      >
        <div className="grid grid-4">
          <Stat label="Cases in mandate" value={fmtNum(data.women_safety?.cases_in_mandate)} />
          <Stat label="Trafficking cases" value={fmtNum(data.women_safety?.trafficking_cases)} accent="var(--critical)" />
          <Stat label="Grave offences" value={fmtNum(data.women_safety?.grave_cases)} accent="var(--high)" />
          <Stat label="Pending investigation" value={fmtNum(data.women_safety?.pending_investigation)} />
        </div>
      </Card>
    </>
  );
}
