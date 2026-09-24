import React from "react";
import { login } from "../lib/api";
import { ErrorBox } from "../components/ui";

const CREDENTIALS = [
  { role: "Administrator", username: "admin", password: "admin123!", note: "full access + tamper demo" },
  { role: "Investigator", username: "investigator", password: "invest123!", note: "PII visible, can run simulations" },
  { role: "Analyst", username: "analyst", password: "analyst123!", note: "analysis only, PII masked" },
  { role: "Viewer", username: "viewer", password: "viewer123!", note: "read-only, PII masked" },
];

export default function Login({ onSuccess }) {
  const [username, setUsername] = React.useState("investigator");
  const [password, setPassword] = React.useState("invest123!");
  const [error, setError] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      onSuccess();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-head">
          <div className="login-mark">भा</div>
          <h1 style={{ fontSize: 17, margin: "0 0 4px" }}>Criminal Network Analysis System</h1>
          <div className="dim" style={{ fontSize: 11.5, lineHeight: 1.5 }}>
            National Crime Records Bureau · Women Safety Division
            <br />
            Ministry of Home Affairs, Government of India
          </div>
        </div>

        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="u">Username</label>
            <input id="u" className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
          </div>
          <div className="field">
            <label htmlFor="p">Password</label>
            <input id="p" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          {error && <ErrorBox error={error} />}
          <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: "100%", marginTop: 8, padding: "9px" }}>
            {busy ? "Authenticating…" : "Sign in"}
          </button>
        </form>

        <div className="cred-grid">
          <div className="dim" style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 2 }}>
            Demonstration accounts — click to fill
          </div>
          {CREDENTIALS.map((c) => (
            <div
              key={c.username}
              className="cred-row"
              onClick={() => {
                setUsername(c.username);
                setPassword(c.password);
              }}
            >
              <span>
                <strong>{c.role}</strong> <span className="dim">· {c.note}</span>
              </span>
              <span className="mono dim">{c.username}</span>
            </div>
          ))}
        </div>

        <div className="dim" style={{ fontSize: 10.5, marginTop: 14, lineHeight: 1.55 }}>
          Every access to a case or citizen record is written to an append-only,
          hash-linked audit ledger. Roles without the <code className="inline">read:pii</code>{" "}
          permission see masked identifiers.
        </div>
      </div>
    </div>
  );
}
