import React from "react";
import { api } from "../lib/api";
import {
  Bar, Card, Chip, ErrorBox, Loading, PageHead, Stat, Tabs, fmtNum, useApi,
} from "../components/ui";

/** Women Safety Division module — department-specific analysis. */
export default function WomenSafety({ onNavigate }) {
  const [tab, setTab] = React.useState("overview");
  const { data, error, loading, refresh } = useApi(() => api.womenSafety());

  if (loading) return <Loading label="Loading Women Safety Division analysis…" />;
  if (error) return <ErrorBox error={error} onRetry={refresh} />;
  if (!data) return null;

  const o = data.overview;

  return (
    <>
      <PageHead
        title="Women Safety Division"
        desc="Analysis specific to the division's statutory mandate: repeat and cross-jurisdictional offenders, offence-escalation risk, trafficking corridors, and district hotspots for resource allocation."
      />

      <div className="grid grid-6" style={{ marginBottom: 12 }}>
        <Stat label="Cases in mandate" value={fmtNum(o.cases_in_mandate)} sub={`${o.mandate_share_pct}% of all cases`} />
        <Stat label="Trafficking cases" value={fmtNum(o.trafficking_cases)} accent="var(--critical)" />
        <Stat label="Grave offences" value={fmtNum(o.grave_cases)} sub="gravity ≥ 9/10" accent="var(--high)" />
        <Stat label="Repeat offenders" value={fmtNum(data.repeat_offender_count)} accent="var(--high)" />
        <Stat label="Cross-jurisdictional" value={fmtNum(data.cross_jurisdictional_offenders)} sub="span multiple states" accent="var(--critical)" />
        <Stat label="Escalation watchlist" value={fmtNum(data.escalation_watchlist.length)} sub="preventable escalation" accent="var(--medium)" />
      </div>

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: "overview", label: "Case overview", count: o.cases_in_mandate },
          { id: "repeat", label: "Repeat offenders", count: data.repeat_offender_count },
          { id: "escalation", label: "Escalation watchlist", count: data.escalation_watchlist.length },
          { id: "corridors", label: "Trafficking corridors", count: data.trafficking_corridors.length },
          { id: "hotspots", label: "Hotspots", count: data.hotspots.length },
        ]}
      />

      {tab === "overview" && (
        <div className="grid grid-2">
          <Card title="Cases within mandate" note="Sorted by offence gravity.">
            <div className="tbl-wrap" style={{ maxHeight: 480 }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>FIR</th>
                    <th>Offences</th>
                    <th>Jurisdiction</th>
                    <th className="num">Gravity</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {o.cases.map((c) => (
                    <tr key={c.fir_id} className="clickable" onClick={() => onNavigate("case", c.fir_id)}>
                      <td className="mono" style={{ color: "var(--accent)" }}>{c.fir_id}</td>
                      <td className="wrap-text" style={{ fontSize: 11.5 }}>{c.offences.join("; ")}</td>
                      <td className="dim">{c.district}, {c.state}</td>
                      <td className="num mono">{c.max_gravity}/10</td>
                      <td style={{ fontSize: 11.5 }}>{c.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="stack">
            <Card title="Offence domain distribution">
              {Object.entries(o.by_offence_domain).map(([domain, count]) => (
                <div className="factor-row" key={domain}>
                  <span>{domain}</span>
                  <Bar value={count} max={Math.max(...Object.values(o.by_offence_domain))} color="var(--high)" />
                  <span className="num mono">{count}</span>
                </div>
              ))}
            </Card>
            <Card title="Geographic distribution" note="Cases within mandate by state.">
              {Object.entries(o.by_state).map(([state, count]) => (
                <div className="factor-row" key={state}>
                  <span>{state}</span>
                  <Bar value={count} max={Math.max(...Object.values(o.by_state))} color="var(--accent)" />
                  <span className="num mono">{count}</span>
                </div>
              ))}
            </Card>
          </div>
        </div>
      )}

      {tab === "repeat" && (
        <Card
          title="Repeat offenders"
          note="Cross-jurisdictional repetition is flagged separately because no single police station can see the full pattern — this is precisely the gap a central system closes."
        >
          <div className="tbl-wrap" style={{ maxHeight: "calc(100vh - 400px)" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Individual</th>
                  <th className="num">Cases</th>
                  <th>Jurisdictions</th>
                  <th className="num">Gravity</th>
                  <th>Priority</th>
                  <th>Assessment</th>
                </tr>
              </thead>
              <tbody>
                {data.repeat_offenders.map((r) => (
                  <tr key={r.entity_id} className="clickable" onClick={() => onNavigate("entity", r.entity_id)}>
                    <td style={{ color: "var(--accent)" }}>{r.name}</td>
                    <td className="num mono">{r.case_count}</td>
                    <td className="dim" style={{ fontSize: 11.5 }}>
                      {r.states.join(", ")}
                      {r.cross_jurisdictional && (
                        <div style={{ marginTop: 2 }}>
                          <Chip kind="critical">Cross-state</Chip>
                        </div>
                      )}
                    </td>
                    <td className="num mono">{r.max_gravity}/10</td>
                    <td>
                      <Chip kind={r.priority}>{r.priority}</Chip>
                    </td>
                    <td className="wrap-text dim" style={{ fontSize: 11.5 }}>{r.assessment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {tab === "escalation" && (
        <Card
          title="Escalation watchlist"
          note="Offences are placed on an escalation ladder. Multiple precursor offences without a grave offence yet is the window where preventive action changes the outcome."
        >
          <div className="tbl-wrap" style={{ maxHeight: "calc(100vh - 400px)" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Individual</th>
                  <th className="num">Ladder position</th>
                  <th>Precursor offences</th>
                  <th className="num">Escalation score</th>
                  <th>Recommendation</th>
                </tr>
              </thead>
              <tbody>
                {data.escalation_watchlist.map((e) => (
                  <tr key={e.entity_id} className="clickable" onClick={() => onNavigate("entity", e.entity_id)}>
                    <td style={{ color: "var(--accent)" }}>{e.name}</td>
                    <td className="num mono">{e.current_ladder_position}/10</td>
                    <td className="mono dim" style={{ fontSize: 11 }}>{e.precursor_offences.join(", ")}</td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        <span className="mono">{e.escalation_score}</span>
                        <Bar value={e.escalation_score} />
                      </div>
                    </td>
                    <td className="wrap-text dim" style={{ fontSize: 11.5 }}>{e.recommendation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.escalation_watchlist.length === 0 && (
            <div className="empty">No individuals currently meet the escalation-risk criteria in this corpus.</div>
          )}
        </Card>
      )}

      {tab === "corridors" && (
        <Card title="Inferred trafficking corridors" note="Location pairs that recur across trafficking cases. A corridor is operationally actionable in a way that individual case locations are not.">
          {data.trafficking_corridors.length === 0 ? (
            <div className="empty">No recurring corridors identified in this corpus.</div>
          ) : (
            <table className="tbl">
              <thead>
                <tr>
                  <th>Origin</th>
                  <th>Destination</th>
                  <th className="num">Cases</th>
                  <th>States</th>
                  <th>Assessment</th>
                </tr>
              </thead>
              <tbody>
                {data.trafficking_corridors.map((c, i) => (
                  <tr key={i}>
                    <td>{c.origin}</td>
                    <td>{c.destination}</td>
                    <td className="num mono">{c.case_count}</td>
                    <td className="dim">
                      {c.states.join(", ")}
                      {c.interstate && (
                        <div style={{ marginTop: 2 }}>
                          <Chip kind="critical">Interstate</Chip>
                        </div>
                      )}
                    </td>
                    <td className="wrap-text dim" style={{ fontSize: 11.5 }}>{c.assessment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {tab === "hotspots" && (
        <Card title="District hotspot index" note="Composite of case volume, offence severity and investigation backlog — intended for resource allocation decisions.">
          <table className="tbl">
            <thead>
              <tr>
                <th>District</th>
                <th>State</th>
                <th className="num">Cases</th>
                <th className="num">Grave</th>
                <th className="num">Pending</th>
                <th className="num">Avg gravity</th>
                <th style={{ width: 150 }}>Hotspot index</th>
                <th>Band</th>
              </tr>
            </thead>
            <tbody>
              {data.hotspots.map((h, i) => (
                <tr key={i}>
                  <td>{h.district}</td>
                  <td className="dim">{h.state}</td>
                  <td className="num mono">{h.case_count}</td>
                  <td className="num mono">{h.grave_case_count}</td>
                  <td className="num mono">{h.pending_investigation}</td>
                  <td className="num mono">{h.avg_gravity}</td>
                  <td>
                    <div className="row" style={{ gap: 6 }}>
                      <span className="mono">{h.hotspot_index}</span>
                      <Bar value={h.hotspot_index} />
                    </div>
                  </td>
                  <td>
                    <Chip kind={h.band}>{h.band}</Chip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );
}
