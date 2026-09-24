import React from "react";

/* Shared presentational primitives. Kept deliberately small — this project
   avoids a component library so the whole UI is inspectable. */

export function Loading({ label = "Loading…" }) {
  return (
    <div className="loading">
      <div className="spinner" />
      <div>{label}</div>
    </div>
  );
}

export function ErrorBox({ error, onRetry }) {
  if (!error) return null;
  return (
    <div className="error-box">
      <strong>Error:</strong> {String(error.message || error)}
      {onRetry && (
        <>
          {" "}
          <button className="btn btn-sm" onClick={onRetry} style={{ marginLeft: 8 }}>
            Retry
          </button>
        </>
      )}
    </div>
  );
}

export function Empty({ label = "No records" }) {
  return <div className="empty">{label}</div>;
}

export function Card({ title, note, actions, children, style }) {
  return (
    <div className="card" style={style}>
      {(title || actions) && (
        <div className="card-head">
          <div>
            {title && <h3 className="card-title">{title}</h3>}
            {note && <p className="card-note">{note}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}

export function Stat({ label, value, sub, accent }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function Chip({ kind = "neutral", children }) {
  const key = String(kind).toLowerCase();
  const cls =
    {
      critical: "chip-critical",
      high: "chip-high",
      medium: "chip-medium",
      moderate: "chip-moderate",
      low: "chip-low",
      minimal: "chip-minimal",
      info: "chip-info",
    }[key] || "chip-neutral";
  return <span className={`chip ${cls}`}>{children}</span>;
}

export function Bar({ value, max = 100, color }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const c = color || (pct > 70 ? "var(--critical)" : pct > 45 ? "var(--high)" : pct > 22 ? "var(--medium)" : "var(--low)");
  return (
    <div className="bar" title={`${value} / ${max}`}>
      <span style={{ width: `${pct}%`, background: c }} />
    </div>
  );
}

export function PageHead({ title, desc, actions }) {
  return (
    <div className="page-head">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">{title}</h1>
          {desc && <p className="page-desc">{desc}</p>}
        </div>
        {actions}
      </div>
    </div>
  );
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs">
      {tabs.map((t) => (
        <button
          key={t.id}
          className={`tab ${active === t.id ? "active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
          {t.count != null && <span className="dim"> ({t.count})</span>}
        </button>
      ))}
    </div>
  );
}

export function fmtInr(value) {
  const n = Number(value || 0);
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
  if (n >= 1e3) return `₹${(n / 1e3).toFixed(1)}K`;
  return `₹${n.toFixed(0)}`;
}

export function fmtNum(value) {
  return Number(value || 0).toLocaleString("en-IN");
}

export const TYPE_COLORS = {
  Person: "#4a90ff",
  Organization: "#b57bff",
  Phone: "#4ad9a4",
  Vehicle: "#ffd23f",
  BankAccount: "#ff9436",
  Location: "#5ec8d8",
  Email: "#ff7bd0",
  CryptoWallet: "#e8a33d",
  Bank: "#8a9bb8",
};

export function tierColor(tier = "") {
  if (tier.includes("Tier-1")) return "var(--tier1)";
  if (tier.includes("Tier-2")) return "var(--tier2)";
  if (tier.includes("Tier-3")) return "var(--tier3)";
  return "var(--tier4)";
}

/** Data-fetching hook with loading/error states and manual refresh. */
export function useApi(fn, deps = []) {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [nonce, setNonce] = React.useState(0);

  React.useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    Promise.resolve()
      .then(fn)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { data, error, loading, refresh: () => setNonce((n) => n + 1) };
}
