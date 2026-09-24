/**
 * Cross-Jurisdiction Syndicate Radar (OCND / NATGRID)
 */

const CrossJurisdiction = {
  async init() {
    await this.loadAlerts();
  },

  async loadAlerts() {
    const container = document.getElementById("jurisdictionAlertsContainer");
    const countBadge = document.getElementById("jurisdictionAlertsBadge");
    if (!container) return;

    try {
      const res = await fetch("/api/jurisdictions/cross-links", {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      const alerts = data.alerts || [];

      if (countBadge) {
        countBadge.textContent = alerts.length;
      }

      if (alerts.length === 0) {
        container.innerHTML = `<div class="glass-card" style="text-align:center; padding:30px;">No active cross-jurisdictional syndicate overlaps detected.</div>`;
        return;
      }

      container.innerHTML = alerts.map(a => `
        <div class="glass-card" style="margin-bottom:14px; border-left:4px solid ${a.alert_level === 'CRITICAL' ? '#EF4444' : '#F59E0B'};">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
            <div>
              <div style="display:flex; align-items:center; gap:8px;">
                <span class="badge-risk ${a.alert_level.toLowerCase()}">${a.alert_level} MULTI-STATE LINK</span>
                <span style="font-weight:700; font-size:16px; color:var(--text-main);">${a.entity_name}</span>
                <span class="role-badge">${a.entity_label}</span>
              </div>
              <div style="font-size:13px; color:var(--text-muted); margin-top:4px;">
                ${a.summary}
              </div>
            </div>
            <button class="btn btn-primary" style="font-size:12px; padding:6px 12px;" onclick="window.CrossJurisdiction?.inspectEntity('${a.entity_id}')">
              🌐 View Syndicate Graph
            </button>
          </div>

          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:10px; margin-top:12px;">
            ${a.cases.map(c => `
              <div style="background:var(--bg-secondary); padding:10px 14px; border-radius:8px; border:1px solid var(--border-subtle);">
                <div style="font-weight:600; font-size:12px; color:var(--accent-blue);">FIR No. ${c.fir_number}</div>
                <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">Station: <strong>${c.station}</strong> (${c.state})</div>
                <div style="font-size:11px; color:var(--text-dim);">Crime: ${c.crime_category} | Filed: ${c.filed_date}</div>
              </div>
            `).join("")}
          </div>
        </div>
      `).join("");
    } catch (e) {
      console.error("Jurisdiction radar error:", e);
    }
  },

  inspectEntity(entityId) {
    if (window.App && window.App.graphViz) {
      window.App.switchView("graph");
      window.App.graphViz.centerOnNode(entityId);
    }
  }
};

window.CrossJurisdiction = CrossJurisdiction;
