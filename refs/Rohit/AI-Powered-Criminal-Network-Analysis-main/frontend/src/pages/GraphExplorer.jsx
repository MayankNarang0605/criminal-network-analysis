import React from "react";
import { api } from "../lib/api";
import GraphView, { graphControls } from "../components/GraphView";
import {
  Bar, Card, Chip, ErrorBox, Loading, PageHead, useApi, tierColor,
} from "../components/ui";

/**
 * Graph Explorer — the primary investigative surface.
 *
 * Three interaction modes matter operationally:
 *   1. Browse: see the whole network, spot the dense cells.
 *   2. Focus: select an actor, see their ego network and evidence.
 *   3. Connect: pick two actors and ask how they are linked, with the
 *      relationship chain and per-hop confidence spelled out.
 */
export default function GraphExplorer({ focusId, onNavigate }) {
  const [personOnly, setPersonOnly] = React.useState(true);
  const [layout, setLayout] = React.useState("cose-bilkent");
  const [colorBy, setColorBy] = React.useState("type");
  const [selected, setSelected] = React.useState(focusId || null);
  const [pathSource, setPathSource] = React.useState("");
  const [pathTarget, setPathTarget] = React.useState("");
  const [pathResult, setPathResult] = React.useState(null);
  const [pathBusy, setPathBusy] = React.useState(false);
  const [pathError, setPathError] = React.useState(null);

  const graph = useApi(() => api.graphOverview(personOnly, 500), [personOnly]);
  const detail = useApi(
    () => (selected ? api.entity(selected, 1) : Promise.resolve(null)),
    [selected]
  );

  React.useEffect(() => {
    if (focusId) setSelected(focusId);
  }, [focusId]);

  const nodeIndex = React.useMemo(() => {
    const m = new Map();
    (graph.data?.nodes || []).forEach((n) => m.set(n.id, n));
    return m;
  }, [graph.data]);

  async function findPath() {
    if (!pathSource || !pathTarget) return;
    setPathBusy(true);
    setPathError(null);
    setPathResult(null);
    try {
      const r = await api.path(pathSource, pathTarget, 3);
      setPathResult(r);
      if (!r.found) setPathError(new Error(r.message || "No connecting path found."));
    } catch (e) {
      setPathError(e);
    } finally {
      setPathBusy(false);
    }
  }

  const highlight = pathResult?.paths?.[0]?.path || [];

  return (
    <>
      <PageHead
        title="Graph Explorer"
        desc="Relationship map across all resolved entities. Node size encodes command influence, border colour encodes risk, and edge thickness encodes evidential weight."
      />

      <div className="graph-shell">
        <div className="graph-canvas">
          <div className="graph-toolbar">
            <button
              className={`btn btn-sm ${personOnly ? "btn-primary" : ""}`}
              onClick={() => setPersonOnly((v) => !v)}
            >
              {personOnly ? "Persons only" : "All entity types"}
            </button>
            <select className="input" style={{ width: 150 }} value={layout} onChange={(e) => setLayout(e.target.value)}>
              {graphControls().map((l) => (
                <option key={l} value={l}>
                  Layout: {l}
                </option>
              ))}
            </select>
            <select className="input" style={{ width: 148 }} value={colorBy} onChange={(e) => setColorBy(e.target.value)}>
              <option value="type">Colour: entity type</option>
              <option value="community">Colour: detected cell</option>
            </select>
            <span className="chip chip-neutral">
              {graph.data?.stats?.node_count ?? 0} nodes · {graph.data?.stats?.edge_count ?? 0} edges
            </span>
            {selected && (
              <button className="btn btn-sm" onClick={() => setSelected(null)}>
                Clear focus
              </button>
            )}
          </div>

          {graph.loading ? (
            <Loading label="Laying out network…" />
          ) : graph.error ? (
            <div style={{ padding: 16 }}>
              <ErrorBox error={graph.error} onRetry={graph.refresh} />
            </div>
          ) : (
            <GraphView
              nodes={graph.data?.nodes || []}
              edges={graph.data?.edges || []}
              onSelect={setSelected}
              selectedId={selected}
              highlightPath={highlight}
              layoutName={layout}
              colorBy={colorBy}
            />
          )}
        </div>

        <div className="graph-side">
          <Card title="Connection finder" note="How are two actors linked, and how strong is each hop?">
            <div className="stack">
              <select className="input" value={pathSource} onChange={(e) => setPathSource(e.target.value)}>
                <option value="">Select source actor…</option>
                {[...nodeIndex.values()]
                  .filter((n) => n.type === "Person")
                  .sort((a, b) => b.kingpin_score - a.kingpin_score)
                  .map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label}
                    </option>
                  ))}
              </select>
              <select className="input" value={pathTarget} onChange={(e) => setPathTarget(e.target.value)}>
                <option value="">Select target actor…</option>
                {[...nodeIndex.values()]
                  .filter((n) => n.type === "Person")
                  .sort((a, b) => b.kingpin_score - a.kingpin_score)
                  .map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.label}
                    </option>
                  ))}
              </select>
              <div className="btn-row">
                <button className="btn btn-primary btn-sm" onClick={findPath} disabled={!pathSource || !pathTarget || pathBusy}>
                  {pathBusy ? "Tracing…" : "Trace connection"}
                </button>
                {pathResult && (
                  <button
                    className="btn btn-sm"
                    onClick={() => {
                      setPathResult(null);
                      setPathError(null);
                    }}
                  >
                    Clear
                  </button>
                )}
              </div>
              {pathError && <ErrorBox error={pathError} />}
              {pathResult?.found &&
                pathResult.paths.map((p, i) => (
                  <div key={i} className="evidence">
                    <div className="row" style={{ gap: 6, marginBottom: 4 }}>
                      <strong style={{ color: "var(--text)" }}>Route {i + 1}</strong>
                      <Chip kind="info">{p.length} hops</Chip>
                      <Chip kind={p.path_confidence > 0.7 ? "low" : p.path_confidence > 0.4 ? "medium" : "high"}>
                        {(p.path_confidence * 100).toFixed(0)}% confidence
                      </Chip>
                    </div>
                    {p.hops.map((h, j) => (
                      <div key={j} style={{ marginBottom: 2 }}>
                        <span style={{ color: "var(--text)" }}>{h.from_name}</span>
                        <span className="dim"> —[{(h.rel_types[0] || "").replace(/_/g, " ").toLowerCase()}]→ </span>
                        <span style={{ color: "var(--text)" }}>{h.to_name}</span>
                        <span className="dim mono"> {(h.confidence * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                ))}
            </div>
          </Card>

          {selected && detail.loading && <Loading label="Loading actor…" />}
          {selected && detail.data && (
            <ActorPanel data={detail.data} onNavigate={onNavigate} onSelect={setSelected} />
          )}
          {!selected && (
            <Card title="No actor selected" note="Click any node in the graph to inspect its profile, evidence trail and ego network." />
          )}
        </div>
      </div>
    </>
  );
}

function ActorPanel({ data, onNavigate, onSelect }) {
  const e = data.entity;
  const k = data.kingpin_assessment;
  return (
    <>
      <Card
        title={e.name}
        note={`${e.type} · ${e.entity_id}`}
        actions={
          <button className="btn btn-sm btn-primary" onClick={() => onNavigate("entity", e.entity_id)}>
            Full dossier
          </button>
        }
      >
        <div className="row" style={{ gap: 6, marginBottom: 9 }}>
          <Chip kind={e.risk_band}>Risk {Number(e.risk_score).toFixed(0)}</Chip>
          {k && (
            <span className="chip chip-neutral" style={{ color: tierColor(k.tier) }}>
              {k.tier}
            </span>
          )}
          {data.community && <Chip kind="info">{data.community.label}</Chip>}
        </div>

        {k && (
          <>
            <div className="dim" style={{ fontSize: 11, marginBottom: 5 }}>
              Influence score {k.kingpin_score.toFixed(1)} / 100
            </div>
            {Object.entries(k.contributions).map(([factor, pts]) => (
              <div className="factor-row" key={factor}>
                <span className="dim">{factor.replace(/_/g, " ")}</span>
                <Bar value={pts} max={26} />
                <span className="num mono">{pts.toFixed(1)}</span>
              </div>
            ))}
            <div className="evidence" style={{ marginTop: 8 }}>
              {k.explanation}
            </div>
          </>
        )}

        <dl className="kv" style={{ marginTop: 9 }}>
          <dt>Relationships</dt>
          <dd className="mono">{data.relationship_count}</dd>
          <dt>Linked cases</dt>
          <dd className="mono">{data.cases.length}</dd>
          <dt>Pattern hits</dt>
          <dd className="mono">{data.patterns.length}</dd>
          {e.aliases?.length > 0 && (
            <>
              <dt>Recorded as</dt>
              <dd>{e.aliases.join(", ")}</dd>
            </>
          )}
        </dl>
      </Card>

      <Card title="Direct associations" note="Ordered by evidential confidence.">
        <div className="scroll-y" style={{ maxHeight: 260 }}>
          <table className="tbl">
            <tbody>
              {data.relationships.slice(0, 25).map((r, i) => {
                const isSource = r.source_id === e.entity_id;
                const otherId = isSource ? r.target_id : r.source_id;
                const otherName = isSource ? r.target_name : r.source_name;
                const otherType = isSource ? r.target_type : r.source_type;
                return (
                  <tr
                    key={i}
                    className={["Person","BankAccount","Phone","Vehicle","Organization"].includes(otherType) ? "clickable" : ""}
                    onClick={() => ["Person","BankAccount","Phone","Vehicle","Organization"].includes(otherType) && onSelect(otherId)}
                  >
                    <td>
                      <div style={{ fontSize: 12 }}>{otherName}</div>
                      <div className="dim" style={{ fontSize: 10.5 }}>
                        {r.rel_type.replace(/_/g, " ").toLowerCase()} · {otherType}
                      </div>
                    </td>
                    <td className="num dim">{(r.confidence * 100).toFixed(0)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
