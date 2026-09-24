import React from "react";
import { api } from "../lib/api";
import {
  Bar, Card, Chip, ErrorBox, Loading, PageHead, Stat, useApi, tierColor, fmtNum,
} from "../components/ui";

/**
 * Key Actor Identification.
 *
 * The centrepiece analytical claim: naive centrality mistakes couriers for
 * bosses. This page shows the composite ranking, the factor attribution behind
 * each score, and the disruption simulator that converts the analysis into an
 * arrest recommendation.
 */
export default function Kingpins({ onNavigate }) {
  const { data, error, loading, refresh } = useApi(() => api.kingpins(25));
  const [selected, setSelected] = React.useState([]);
  const [sim, setSim] = React.useState(null);
  const [simBusy, setSimBusy] = React.useState(false);
  const [simError, setSimError] = React.useState(null);
  const [optimal, setOptimal] = React.useState(null);

  function toggle(id) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
    setSim(null);
  }

  async function runSim() {
    setSimBusy(true);
    setSimError(null);
    try {
      setSim(await api.simulate(selected));
    } catch (e) {
      setSimError(e);
    } finally {
      setSimBusy(false);
    }
  }

  async function runOptimal() {
    setSimBusy(true);
    setSimError(null);
    try {
      const r = await api.optimalDisruption(3);
      setOptimal(r);
      setSim(r.simulation);
      setSelected(r.recommended_arrests.map((a) => a.entity_id));
    } catch (e) {
      setSimError(e);
    } finally {
      setSimBusy(false);
    }
  }

  if (loading) return <Loading label="Ranking command-tier actors…" />;
  if (error) return <ErrorBox error={error} onRetry={refresh} />;

  const ranking = data?.ranking || [];

  return (
    <>
      <PageHead
        title="Key Actor Identification"
        desc="Composite Kingpin Influence Score over six orthogonal signals. Single-metric ranking is deliberately avoided: high-volume couriers dominate degree and call-count measures, while genuine leadership is structurally insulated from operational activity."
      />

      <Card title="Scoring methodology" note={data?.methodology} style={{ marginBottom: 12 }}>
        <div className="grid grid-6">
          {Object.entries(data?.weights || {}).map(([factor, weight]) => (
            <Stat
              key={factor}
              label={factor.replace(/_/g, " ")}
              value={`${(weight * 100).toFixed(0)}%`}
              sub={FACTOR_NOTES[factor]}
            />
          ))}
        </div>
      </Card>

      <div className="grid grid-2">
        <Card
          title={`Ranked actors (${ranking.length})`}
          note="Select actors to simulate the effect of arresting them."
          actions={
            <div className="btn-row">
              <button className="btn btn-sm" onClick={runOptimal} disabled={simBusy}>
                Recommend arrest set
              </button>
              <button className="btn btn-sm btn-primary" onClick={runSim} disabled={!selected.length || simBusy}>
                {simBusy ? "Simulating…" : `Simulate (${selected.length})`}
              </button>
            </div>
          }
        >
          <div className="tbl-wrap" style={{ maxHeight: 560 }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: 26 }} />
                  <th>#</th>
                  <th>Actor</th>
                  <th>Tier</th>
                  <th style={{ width: 128 }}>Influence</th>
                  <th>Insulation</th>
                  <th>Damage if removed</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((k) => (
                  <tr key={k.entity_id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.includes(k.entity_id)}
                        onChange={() => toggle(k.entity_id)}
                        aria-label={`Select ${k.name}`}
                      />
                    </td>
                    <td className="dim mono">{k.rank}</td>
                    <td className="clickable" onClick={() => onNavigate("entity", k.entity_id)}>
                      <div style={{ fontWeight: 600, color: "var(--accent)" }}>{k.name}</div>
                      <div className="dim mono" style={{ fontSize: 10.5 }}>{k.entity_id}</div>
                    </td>
                    <td>
                      <span style={{ color: tierColor(k.tier), fontSize: 11.5, fontWeight: 600 }}>
                        {k.tier.replace(/ \(.*\)/, "")}
                      </span>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        <span className="mono">{k.kingpin_score.toFixed(1)}</span>
                        <Bar value={k.kingpin_score} />
                      </div>
                    </td>
                    <td className="num mono">{k.insulation_index.toFixed(2)}</td>
                    <td className="num mono">{(k.network_damage_if_removed * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="stack">
          {simError && <ErrorBox error={simError} />}

          {optimal && (
            <Card
              title="Recommended arrest set"
              note="Greedy maximisation of network fragmentation per arrest. Greedy is near-optimal for this submodular objective and stays tractable, unlike exhaustive search."
            >
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Step</th>
                    <th>Actor</th>
                    <th>Marginal fragmentation</th>
                  </tr>
                </thead>
                <tbody>
                  {optimal.recommended_arrests.map((a) => (
                    <tr key={a.entity_id} className="clickable" onClick={() => onNavigate("entity", a.entity_id)}>
                      <td className="mono dim">{a.step}</td>
                      <td>{a.name}</td>
                      <td className="num mono">+{a.marginal_fragmentation.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}

          {sim && !sim.error && (
            <Card title="Disruption simulation" note={sim.assessment}>
              <div className="grid grid-3" style={{ marginBottom: 10 }}>
                <Stat
                  label="Fragmentation"
                  value={`${sim.impact.fragmentation_pct.toFixed(1)}%`}
                  accent={sim.impact.fragmentation_pct > 40 ? "var(--low)" : "var(--high)"}
                  sub="loss of internal reachability"
                />
                <Stat label="Edges severed" value={fmtNum(sim.impact.edges_removed)} sub={`${sim.impact.edges_removed_pct}% of network`} />
                <Stat label="New fragments" value={fmtNum(sim.impact.new_components)} sub="disconnected cells created" />
              </div>

              <table className="tbl" style={{ marginBottom: 8 }}>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th className="num">Before</th>
                    <th className="num">After</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Actors", "nodes"],
                    ["Connections", "edges"],
                    ["Components", "components"],
                    ["Largest cell", "largest_component"],
                    ["Reachable pairs", "reachable_pair_fraction"],
                    ["Average degree", "avg_degree"],
                  ].map(([label, key]) => (
                    <tr key={key}>
                      <td className="dim">{label}</td>
                      <td className="num mono">{formatMetric(sim.before[key])}</td>
                      <td className="num mono" style={{ color: "var(--accent)" }}>
                        {formatMetric(sim.after[key])}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {sim.likely_successor && (
                <div className="evidence">
                  <strong style={{ color: "var(--text)" }}>Succession risk: </strong>
                  {sim.likely_successor.name} becomes the highest-influence surviving actor
                  (score {sim.likely_successor.kingpin_score.toFixed(1)}). Removing leadership
                  without preparing for succession typically produces temporary disruption only.
                </div>
              )}

              {sim.impact.isolated_actors?.length > 0 && (
                <div className="evidence">
                  <strong style={{ color: "var(--text)" }}>Fully isolated: </strong>
                  {sim.impact.isolated_actors.map((a) => a.name).join(", ")}
                </div>
              )}
            </Card>
          )}

          {ranking[0] && (
            <Card title={`Factor attribution — ${ranking[0].name}`} note="Top-ranked actor, points contributed per signal.">
              {Object.entries(ranking[0].contributions).map(([factor, pts]) => (
                <div className="factor-row" key={factor}>
                  <span className="dim">{factor.replace(/_/g, " ")}</span>
                  <Bar value={pts} max={26} />
                  <span className="num mono">{pts.toFixed(1)}</span>
                </div>
              ))}
              <div className="evidence" style={{ marginTop: 8 }}>{ranking[0].explanation}</div>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

const FACTOR_NOTES = {
  betweenness: "controls routes between subgroups",
  eigenvector: "adjacent to other elite actors",
  insulation: "distance from dirty work",
  flow_control: "share of throughput",
  role_breadth: "spans crime domains",
  resilience: "damage on removal",
};

function formatMetric(v) {
  if (typeof v !== "number") return v ?? "—";
  return v < 1 && v > 0 ? v.toFixed(3) : v.toLocaleString("en-IN");
}
