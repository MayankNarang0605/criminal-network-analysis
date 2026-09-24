/**
 * Network Analytics, Key Players Leaderboard, Communities & Link Prediction
 */

const AnalyticsView = {
  currentRankings: [],

  async init() {
    await this.loadKeyPlayers();
    await this.loadCommunities();
    await this.loadLinkPredictions();
    this.setupShortestPathFinder();
  },

  async loadKeyPlayers() {
    const tbody = document.getElementById("keyPlayersTableBody");
    if (!tbody) return;

    try {
      const res = await fetch("/api/analytics/key-players", {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      this.currentRankings = data.rankings || [];

      if (this.currentRankings.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px;">No suspects ranked yet.</td></tr>`;
        return;
      }

      tbody.innerHTML = this.currentRankings.map((p, idx) => {
        const riskClass = p.risk_tier.toLowerCase();
        return `
          <tr>
            <td style="font-weight:700; color:var(--accent-blue);">#${idx + 1}</td>
            <td>
              <div style="font-weight:600; cursor:pointer;" onclick="window.SuspectDossier?.openDossier('${p.id}')">
                ${p.name}
              </div>
              <div style="font-size:11px; color:var(--text-muted);">${p.aliases?.length ? `@ ${p.aliases.join(', ')}` : ''}</div>
            </td>
            <td>
              <span class="badge-risk ${riskClass}">${p.operational_role}</span>
            </td>
            <td>
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-weight:700; font-size:14px; color:${p.risk_score >= 70 ? '#EF4444' : (p.risk_score >= 45 ? '#F59E0B' : '#38BDF8')}">${p.risk_score}</span>
                <div style="width:60px; height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden;">
                  <div style="width:${p.risk_score}%; height:100%; background:${p.risk_score >= 70 ? '#EF4444' : (p.risk_score >= 45 ? '#F59E0B' : '#38BDF8')};"></div>
                </div>
              </div>
            </td>
            <td style="font-family:var(--font-mono); font-size:12px;">${p.centrality_metrics?.pagerank || 0}</td>
            <td style="font-family:var(--font-mono); font-size:12px;">${p.centrality_metrics?.betweenness_centrality || 0}</td>
            <td>
              <button class="btn btn-secondary" style="padding:4px 10px; font-size:11px;" onclick="window.SuspectDossier?.openDossier('${p.id}')">
                🔍 360° Dossier
              </button>
            </td>
          </tr>
        `;
      }).join("");
    } catch (e) {
      console.error("Key players error:", e);
    }
  },

  async loadCommunities() {
    const container = document.getElementById("communitiesContainer");
    if (!container) return;

    try {
      const res = await fetch("/api/analytics/communities", {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      const comms = data.communities || [];

      document.getElementById("modularityScoreBadge").textContent = `Modularity: ${data.modularity_score || 0}`;

      container.innerHTML = comms.map(c => `
        <div class="glass-card" style="border-top:4px solid ${c.color};">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-weight:700; color:var(--text-main); font-size:14px;">${c.label}</span>
            <span class="role-badge" style="background:${c.color}22; color:${c.color}; border-color:${c.color}44;">
              ${c.total_members} Nodes
            </span>
          </div>
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:6px;">
            Primary Focus: <strong style="color:var(--text-main);">${c.primary_focus}</strong>
          </div>
          ${c.leader_candidate ? `
            <div style="font-size:12px; color:var(--text-muted);">
              Key Operative: <strong style="color:var(--accent-blue);">${c.leader_candidate.name}</strong> (Risk: ${c.leader_candidate.risk_score})
            </div>
          ` : ''}
        </div>
      `).join("");
    } catch (e) {
      console.error("Communities error:", e);
    }
  },

  async loadLinkPredictions() {
    const tbody = document.getElementById("linkPredictionsTableBody");
    if (!tbody) return;

    try {
      const res = await fetch("/api/analytics/link-predictions?top_k=10", {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      const preds = data.predictions || [];

      if (preds.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px;">No missing links predicted.</td></tr>`;
        return;
      }

      tbody.innerHTML = preds.map(p => `
        <tr>
          <td>
            <strong style="color:var(--accent-blue);">${p.source_name}</strong>
            <span class="role-badge" style="font-size:9px; padding:1px 5px; margin-left:4px;">${p.source_label}</span>
          </td>
          <td>
            <strong style="color:var(--accent-amber);">${p.target_name}</strong>
            <span class="role-badge" style="font-size:9px; padding:1px 5px; margin-left:4px;">${p.target_label}</span>
          </td>
          <td>
            <div style="display:flex; align-items:center; gap:6px;">
              <span style="font-weight:700; color:var(--accent-emerald);">${Math.round(p.confidence_score * 100)}%</span>
            </div>
          </td>
          <td style="font-size:12px; color:var(--text-muted); max-width:300px;">
            ${p.evidence_explanation}
          </td>
          <td>
            <button class="btn btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="window.AnalyticsView?.showShortestPath('${p.source_id}', '${p.target_id}')">
              ⚡ Trace Path
            </button>
          </td>
        </tr>
      `).join("");
    } catch (e) {
      console.error("Link prediction error:", e);
    }
  },

  setupShortestPathFinder() {
    const form = document.getElementById("shortestPathForm");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const src = document.getElementById("pathSourceSelect").value;
      const dst = document.getElementById("pathTargetSelect").value;
      if (src && dst) {
        await this.showShortestPath(src, dst);
      }
    });
  },

  async showShortestPath(sourceId, targetId) {
    try {
      const res = await fetch(`/api/analytics/shortest-path?source_id=${sourceId}&target_id=${targetId}`, {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      const resultContainer = document.getElementById("shortestPathResult");

      if (!data.found) {
        if (resultContainer) {
          resultContainer.innerHTML = `<div class="toast error" style="position:static;">${data.message}</div>`;
        }
        window.App?.showToast(data.message, "error");
        return;
      }

      // Highlight on Graph Visualizer
      if (window.App && window.App.graphViz) {
        window.App.switchView("graph");
        window.App.graphViz.highlightPathRoute(data.path_node_ids);
      }

      if (resultContainer) {
        resultContainer.innerHTML = `
          <div class="glass-card" style="border:1px solid var(--accent-amber); margin-top:12px;">
            <div style="font-weight:700; color:var(--accent-amber); margin-bottom:8px;">
              ✓ Shortest Relational Chain Found (${data.hop_distance} Hops)
            </div>
            <div style="display:flex; flex-direction:column; gap:6px;">
              ${data.step_explanations.map(s => `
                <div style="font-size:12px; padding:6px 10px; background:var(--bg-secondary); border-radius:6px;">
                  <strong>Step ${s.step}:</strong> ${s.detail}
                </div>
              `).join("")}
            </div>
          </div>
        `;
      }
      window.App?.showToast(`Chain found across ${data.hop_distance} hops! Route highlighted in Graph.`, "success");
    } catch (e) {
      console.error("Path error:", e);
    }
  }
};

window.AnalyticsView = AnalyticsView;
