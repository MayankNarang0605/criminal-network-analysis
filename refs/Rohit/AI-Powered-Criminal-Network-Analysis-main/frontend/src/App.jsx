import React from "react";
import { api, getUser, isAuthenticated, logout } from "./lib/api";
import { Chip, useApi } from "./components/ui";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import GraphExplorer from "./pages/GraphExplorer";
import Kingpins from "./pages/Kingpins";
import Patterns from "./pages/Patterns";
import EntityDossier from "./pages/EntityDossier";
import Cases from "./pages/Cases";
import WomenSafety from "./pages/WomenSafety";
import LiveInvestigation from "./pages/LiveInvestigation";
import {
  Alerts, AuditLedger, Communities, Evaluation, LinkPrediction, Search,
} from "./pages/Misc";

const NAV = [
  {
    group: "Intelligence",
    items: [
      { id: "dashboard", label: "Overview", icon: "▤" },
      { id: "graph", label: "Graph Explorer", icon: "◈" },
      { id: "kingpins", label: "Key Actors", icon: "★" },
      { id: "communities", label: "Criminal Cells", icon: "◍" },
      { id: "predict", label: "Hidden Links", icon: "⟿" },
    ],
  },
  {
    group: "Detection",
    items: [
      { id: "patterns", label: "Suspicious Patterns", icon: "⚠" },
      { id: "alerts", label: "Alert Worklist", icon: "◉", badgeKey: "alerts" },
    ],
  },
  {
    group: "Records",
    items: [
      { id: "cases", label: "Case Register", icon: "▣", badgeKey: "cases" },
      { id: "live", label: "Live Investigation", icon: "✚" },
      { id: "search", label: "Global Search", icon: "⌕" },
    ],
  },
  {
    group: "Division",
    items: [{ id: "women", label: "Women Safety", icon: "⚖" }],
  },
  {
    group: "Assurance",
    items: [
      { id: "evaluation", label: "Model Evaluation", icon: "◎" },
      { id: "audit", label: "Audit Ledger", icon: "⛓" },
    ],
  },
];

const TITLES = {
  dashboard: ["Operational Overview", "Consolidated intelligence picture"],
  graph: ["Graph Explorer", "Relationship mapping and path tracing"],
  kingpins: ["Key Actor Identification", "Command-tier ranking and disruption planning"],
  communities: ["Criminal Cell Detection", "Community structure analysis"],
  predict: ["Hidden Connection Discovery", "Link prediction over the association network"],
  patterns: ["Suspicious Pattern Detection", "FATF / FIU-IND typologies and behavioural signatures"],
  alerts: ["Alert Worklist", "Prioritised investigative queue"],
  cases: ["Case Register", "FIR records and narrative intelligence"],
  live: ["Live Investigation", "Add FIR/CDR/Ledger from dashboard — no file editing"],
  search: ["Global Search", "Cross-source retrieval"],
  women: ["Women Safety Division", "Department-specific analysis"],
  evaluation: ["Model Evaluation", "Ground-truth accuracy measurement"],
  audit: ["Blockchain Audit Ledger", "Tamper-evident access accountability"],
  entity: ["Entity Dossier", "Consolidated actor profile"],
  case: ["Case Record", "Full FIR with extracted intelligence"],
};

export default function App() {
  const [authed, setAuthed] = React.useState(isAuthenticated());
  const [view, setView] = React.useState("dashboard");
  const [param, setParam] = React.useState(null);
  const stats = useApi(() => (authed ? api.stats() : Promise.resolve(null)), [authed, view]);

  const navigate = React.useCallback((next, arg = null) => {
    setView(next);
    setParam(arg);
    document.querySelector(".main")?.scrollTo({ top: 0 });
  }, []);

  if (!authed) return <Login onSuccess={() => setAuthed(true)} />;

  const user = getUser();
  const [title, subtitle] = TITLES[view] || ["", ""];
  const badges = {
    alerts: stats.data?.alerts,
    cases: stats.data?.cases,
  };

  return (
    <div className="app">
      <div className="brand">
        <div className="brand-mark">भा</div>
        <div className="brand-text">
          <div className="brand-title">NCRB · CNAS</div>
          <div className="brand-sub">MHA · Govt of India</div>
        </div>
      </div>

      <header className="header">
        <div>
          <div className="header-title">{title}</div>
          <div className="header-sub">{subtitle}</div>
        </div>
        <div className="header-spacer" />
        {stats.data && (
          <div className="row" style={{ gap: 6 }}>
            <span className="chip chip-neutral">{stats.data.entities} entities</span>
            <span className="chip chip-neutral">{stats.data.relationships} links</span>
            <span className="chip chip-info">{stats.data.audit_blocks} audit blocks</span>
          </div>
        )}
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 12, fontWeight: 600 }}>{user?.full_name}</div>
          <div className="dim" style={{ fontSize: 10.5 }}>
            {user?.role} · {user?.unit}
          </div>
        </div>
        <button
          className="btn btn-sm"
          onClick={() => {
            logout();
            setAuthed(false);
          }}
        >
          Sign out
        </button>
      </header>

      <nav className="nav">
        {NAV.map((group) => (
          <div className="nav-group" key={group.group}>
            <div className="nav-group-label">{group.group}</div>
            {group.items.map((item) => (
              <button
                key={item.id}
                className={`nav-item ${view === item.id ? "active" : ""}`}
                onClick={() => navigate(item.id)}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
                {item.badgeKey && badges[item.badgeKey] != null && (
                  <span className="nav-badge">{badges[item.badgeKey]}</span>
                )}
              </button>
            ))}
          </div>
        ))}
      </nav>

      <main className="main">
        {view === "dashboard" && <Dashboard onNavigate={navigate} />}
        {view === "graph" && <GraphExplorer focusId={param} onNavigate={navigate} />}
        {view === "kingpins" && <Kingpins onNavigate={navigate} />}
        {view === "communities" && <Communities onNavigate={navigate} />}
        {view === "predict" && <LinkPrediction onNavigate={navigate} />}
        {view === "patterns" && <Patterns onNavigate={navigate} />}
        {view === "alerts" && <Alerts onNavigate={navigate} />}
        {view === "cases" && <Cases onNavigate={navigate} />}
        {view === "case" && <Cases caseId={param} onNavigate={navigate} />}
        {view === "live" && <LiveInvestigation onNavigate={navigate} />}
        {view === "search" && <Search onNavigate={navigate} />}
        {view === "women" && <WomenSafety onNavigate={navigate} />}
        {view === "evaluation" && <Evaluation />}
        {view === "audit" && <AuditLedger />}
        {view === "entity" && <EntityDossier entityId={param} onNavigate={navigate} />}
      </main>
    </div>
  );
}
