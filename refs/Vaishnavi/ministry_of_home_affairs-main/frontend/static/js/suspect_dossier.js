/**
 * 360° Suspect Investigation Dossier & Forensic Timeline
 */

const SuspectDossier = {
  currentEntityId: null,

  async openDossier(entityId) {
    this.currentEntityId = entityId;
    const modal = document.getElementById("dossierModal");
    if (!modal) return;

    modal.classList.add("active");
    await this.loadDossierData(entityId);
  },

  closeDossier() {
    const modal = document.getElementById("dossierModal");
    if (modal) modal.classList.remove("active");
  },

  async loadDossierData(entityId) {
    const content = document.getElementById("dossierModalContent");
    if (!content) return;

    content.innerHTML = `<div style="text-align:center; padding:30px;">Loading suspect intelligence record...</div>`;

    try {
      const res = await fetch(`/api/graph/profile/${entityId}`, {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      if (!res.ok) {
        content.innerHTML = `<div class="toast error">${data.error || "Failed to load dossier"}</div>`;
        return;
      }

      const entity = data.entity;
      const associates = data.associates || [];
      const cases = data.connected_cases || [];
      const assets = data.assets || [];
      const timeline = data.timeline || [];
      const riskScore = entity.risk_score || 0;

      content.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:18px; border-bottom:1px solid var(--border-subtle); padding-bottom:14px;">
          <div>
            <div style="display:flex; align-items:center; gap:10px;">
              <span style="font-size:22px; font-weight:700; color:var(--text-main);">${entity.name}</span>
              <span class="role-badge" style="font-size:12px;">${entity.label}</span>
              <span class="badge-risk ${entity.risk_tier ? entity.risk_tier.toLowerCase() : 'low'}">
                ${entity.operational_role || 'Suspect'} (Risk: ${riskScore})
              </span>
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
              ${entity.aliases?.length ? `Known Aliases: <strong>${entity.aliases.join(", ")}</strong>` : 'No known aliases'}
              ${entity.phone ? ` | Mobile: <strong>${entity.phone}</strong>` : ''}
              ${entity.state_origin ? ` | Domicile: <strong>${entity.state_origin}</strong>` : ''}
            </div>
          </div>
          <button class="btn btn-primary" onclick="window.SuspectDossier?.exportReport('${entity.id}')">
            📄 Export Dossier
          </button>
        </div>

        <!-- 3-Column Profile Grid -->
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:14px; margin-bottom:18px;">
          <!-- 1. Direct Associates Tree -->
          <div class="glass-card">
            <div style="font-weight:700; font-size:13px; color:var(--accent-blue); margin-bottom:8px;">
              👥 Direct Associates & Contacts (${associates.length})
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; max-height:160px; overflow-y:auto;">
              ${associates.length ? associates.map(a => `
                <div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg-secondary); padding:6px 10px; border-radius:6px; font-size:12px;">
                  <div>
                    <strong>${a.name}</strong>
                    <div style="font-size:10px; color:var(--text-muted);">${a.relation || 'LINKED'}</div>
                  </div>
                  <span class="role-badge" style="font-size:10px;">${a.role || 'Associate'}</span>
                </div>
              `).join("") : '<div style="font-size:12px; color:var(--text-dim);">No direct associates recorded.</div>'}
            </div>
          </div>

          <!-- 2. Linked Assets & Financials -->
          <div class="glass-card">
            <div style="font-weight:700; font-size:13px; color:var(--accent-purple); margin-bottom:8px;">
              💳 Linked Assets & Accounts (${assets.length})
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; max-height:160px; overflow-y:auto;">
              ${assets.length ? assets.map(ast => `
                <div style="background:var(--bg-secondary); padding:6px 10px; border-radius:6px; font-size:12px;">
                  <strong>${ast.name}</strong>
                  <div style="font-size:10px; color:var(--text-muted);">${ast.type}</div>
                </div>
              `).join("") : '<div style="font-size:12px; color:var(--text-dim);">No physical/financial assets registered.</div>'}
            </div>
          </div>

          <!-- 3. Connected Cases & FIRs -->
          <div class="glass-card">
            <div style="font-weight:700; font-size:13px; color:var(--accent-amber); margin-bottom:8px;">
              📂 Connected FIRs & Cases (${cases.length})
            </div>
            <div style="display:flex; flex-direction:column; gap:6px; max-height:160px; overflow-y:auto;">
              ${cases.length ? cases.map(c => `
                <div style="background:var(--bg-secondary); padding:6px 10px; border-radius:6px; font-size:12px;">
                  <strong>FIR No. ${c.fir_number}</strong>
                  <div style="font-size:10px; color:var(--text-muted);">${c.station} | ${c.crime_category}</div>
                </div>
              `).join("") : '<div style="font-size:12px; color:var(--text-dim);">No active cases linked.</div>'}
            </div>
          </div>
        </div>

        <!-- Forensic Timeline -->
        <div class="glass-card">
          <div style="font-weight:700; font-size:13px; color:var(--accent-cyan); margin-bottom:10px;">
            ⏱️ Chronological Incident & Case Timeline
          </div>
          <div style="display:flex; flex-direction:column; gap:8px;">
            ${timeline.length ? timeline.map(t => `
              <div style="display:flex; gap:12px; align-items:flex-start; font-size:12px; border-left:2px solid var(--accent-cyan); padding-left:10px;">
                <div style="min-width:85px; font-family:var(--font-mono); color:var(--text-muted);">${t.date}</div>
                <div>
                  <strong style="color:var(--text-main);">${t.title}</strong>
                  <div style="color:var(--text-muted); margin-top:2px;">${t.description}</div>
                </div>
              </div>
            `).join("") : '<div style="font-size:12px; color:var(--text-dim);">No timeline events recorded.</div>'}
          </div>
        </div>
      `;
    } catch (e) {
      console.error("Dossier load error:", e);
    }
  },

  async exportReport(entityId) {
    try {
      const res = await fetch(`/api/export/dossier/${entityId}`, {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `MHA_Dossier_${entityId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      window.App?.showToast("Exported intelligence dossier report!", "success");
    } catch (e) {
      console.error("Export error:", e);
    }
  }
};

window.SuspectDossier = SuspectDossier;
