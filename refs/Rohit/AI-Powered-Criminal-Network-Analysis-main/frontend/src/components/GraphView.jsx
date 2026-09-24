import React from "react";
import cytoscape from "cytoscape";
import coseBilkent from "cytoscape-cose-bilkent";
import { TYPE_COLORS } from "./ui";

cytoscape.use(coseBilkent);

/**
 * Network visualiser.
 *
 * Node size encodes kingpin score (command actors read as larger), fill encodes
 * entity type, and border colour encodes risk band. Edge thickness encodes
 * relationship weight. Selected nodes and their incident edges are highlighted
 * while everything else dims, which is what makes a dense graph readable.
 */
export default function GraphView({
  nodes = [],
  edges = [],
  onSelect,
  selectedId,
  highlightPath = [],
  layoutName = "cose-bilkent",
  colorBy = "type",
}) {
  const containerRef = React.useRef(null);
  const cyRef = React.useRef(null);

  // Build/refresh the graph when data changes.
  React.useEffect(() => {
    if (!containerRef.current) return;

    const elements = [
      ...nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.label,
          type: n.type,
          risk: n.risk_score || 0,
          kingpin: n.kingpin_score || 0,
          community: n.community_id ?? -1,
          degree: n.degree || 0,
        },
      })),
      ...edges
        .filter((e) => nodes.some((n) => n.id === e.source) && nodes.some((n) => n.id === e.target))
        .map((e, i) => ({
          data: {
            id: `e${i}`,
            source: e.source,
            target: e.target,
            rel: e.rel_type,
            weight: e.weight || 1,
            confidence: e.confidence ?? 1,
          },
        })),
    ];

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const palette = [
      "#4a90ff", "#ff9436", "#4ad9a4", "#b57bff", "#ffd23f", "#ff7bd0",
      "#5ec8d8", "#e8734a", "#8ad94a", "#d84a7b", "#4ad8d8", "#c8a34a",
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      wheelSensitivity: 0.25,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 8,
            "font-family": "Inter, sans-serif",
            color: "#c8d5e8",
            "text-valign": "bottom",
            "text-margin-y": 3,
            "text-max-width": 78,
            "text-wrap": "ellipsis",
            "background-color": (ele) =>
              colorBy === "community"
                ? palette[(ele.data("community") + palette.length) % palette.length]
                : TYPE_COLORS[ele.data("type")] || "#8a9bb8",
            width: (ele) => 12 + Math.sqrt(ele.data("kingpin") || 0) * 2.6,
            height: (ele) => 12 + Math.sqrt(ele.data("kingpin") || 0) * 2.6,
            "border-width": 1.6,
            "border-color": (ele) => {
              const r = ele.data("risk");
              if (r >= 70) return "#ff4d5e";
              if (r >= 50) return "#ff9436";
              if (r >= 30) return "#ffd23f";
              return "rgba(255,255,255,0.18)";
            },
            "transition-property": "opacity, border-width",
            "transition-duration": "140ms",
          },
        },
        {
          selector: "edge",
          style: {
            width: (ele) => 0.5 + (ele.data("weight") || 0) * 1.6,
            "line-color": "#2b3853",
            "curve-style": "haystack",
            "haystack-radius": 0.2,
            opacity: 0.62,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 3,
            "border-color": "#ffffff",
            "font-size": 10,
            "z-index": 99,
          },
        },
        { selector: ".dim", style: { opacity: 0.09, "text-opacity": 0 } },
        {
          selector: ".hl-node",
          style: {
            "border-width": 3,
            "border-color": "#ffd23f",
            "z-index": 90,
            "font-size": 10,
          },
        },
        {
          selector: ".hl-edge",
          style: { "line-color": "#ffd23f", width: 3, opacity: 1, "z-index": 90 },
        },
        {
          selector: ".neighbour",
          style: { "border-color": "#4a90ff", "border-width": 2.4 },
        },
      ],
      layout: layoutSpec(layoutName, nodes.length),
    });

    cy.on("tap", "node", (evt) => {
      const id = evt.target.id();
      onSelect?.(id);
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass("dim neighbour");
        onSelect?.(null);
      }
    });

    cyRef.current = cy;
    return () => cy.destroy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, layoutName, colorBy]);

  // Focus/dim behaviour on selection.
  React.useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("dim neighbour");
    cy.$(":selected").unselect();
    if (!selectedId) return;
    const node = cy.getElementById(selectedId);
    if (!node || node.empty()) return;
    const hood = node.closedNeighborhood();
    cy.elements().difference(hood).addClass("dim");
    hood.nodes().difference(node).addClass("neighbour");
    node.select();
    cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 0.9) }, { duration: 260 });
  }, [selectedId]);

  // Path highlighting.
  React.useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("hl-node hl-edge");
    if (!highlightPath?.length) return;
    highlightPath.forEach((id) => cy.getElementById(id).addClass("hl-node"));
    for (let i = 0; i < highlightPath.length - 1; i++) {
      const a = highlightPath[i];
      const b = highlightPath[i + 1];
      cy.edges().forEach((e) => {
        const s = e.data("source");
        const t = e.data("target");
        if ((s === a && t === b) || (s === b && t === a)) e.addClass("hl-edge");
      });
    }
    const eles = cy.collection(highlightPath.map((id) => cy.getElementById(id)));
    if (eles.length) cy.animate({ fit: { eles, padding: 70 } }, { duration: 340 });
  }, [highlightPath]);

  return (
    <>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      <div className="graph-legend">
        <div style={{ color: "var(--text-2)", marginBottom: 2, fontWeight: 600 }}>
          Node size = influence · border = risk
        </div>
        {Object.entries(TYPE_COLORS)
          .slice(0, 6)
          .map(([type, color]) => (
            <div className="legend-item" key={type}>
              <span className="legend-dot" style={{ background: color }} />
              <span className="dim">{type}</span>
            </div>
          ))}
      </div>
    </>
  );
}

function layoutSpec(name, count) {
  if (name === "concentric") {
    return {
      name: "concentric",
      concentric: (n) => n.data("kingpin") || 0,
      levelWidth: () => 12,
      minNodeSpacing: 22,
      animate: false,
    };
  }
  if (name === "grid") return { name: "grid", animate: false };
  if (name === "circle") return { name: "circle", animate: false };
  if (name === "breadthfirst")
    return { name: "breadthfirst", spacingFactor: 1.05, animate: false };
  return {
    name: "cose-bilkent",
    animate: false,
    nodeRepulsion: count > 250 ? 5500 : 9000,
    idealEdgeLength: count > 250 ? 55 : 78,
    gravity: 0.28,
    numIter: count > 400 ? 1400 : 2600,
    tile: true,
    randomize: true,
  };
}

export function graphControls() {
  return ["cose-bilkent", "concentric", "breadthfirst", "circle", "grid"];
}
