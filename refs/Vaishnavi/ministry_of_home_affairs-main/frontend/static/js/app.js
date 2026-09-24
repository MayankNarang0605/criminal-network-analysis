/**
 * Master Application Controller & Router
 */

const App = {
  currentView: "graph",
  graphViz: null,

  async init() {
    console.log("Initializing AI-Powered Criminal Network Analysis System...");

    // Initialize Submodules
    await window.Auth?.init();
    
    this.graphViz = new window.NetworkGraphVisualizer("networkCanvas");
    
    this.setupNavigation();
    this.setupGlobalSearch();
    this.setupResetButton();
    this.setupGraphFilters();

    window.CaseIntake?.init();

    // Initial Data Load
    await this.loadGraphData();
    await this.refreshGlobalStats();

    // Handle view switches
    this.switchView("graph");
  },

  setupNavigation() {
    document.querySelectorAll(".nav-item").forEach(item => {
      item.addEventListener("click", (e) => {
        const targetView = e.currentTarget.dataset.view;
        if (targetView) {
          this.switchView(targetView);
        }
      });
    });
  },

  switchView(viewName) {
    this.currentView = viewName;

    // Update Nav
    document.querySelectorAll(".nav-item").forEach(el => {
      el.classList.toggle("active", el.dataset.view === viewName);
    });

    // Update Panels
    document.querySelectorAll(".view-panel").forEach(panel => {
      panel.classList.toggle("active", panel.id === `view-${viewName}`);
    });

    // Trigger view-specific loads
    if (viewName === "graph") {
      this.graphViz?.resizeCanvas();
    } else if (viewName === "analytics") {
      window.AnalyticsView?.init();
    } else if (viewName === "jurisdictions") {
      window.CrossJurisdiction?.init();
    } else if (viewName === "audit") {
      window.AuditLogs?.init();
    }
  },

  refreshCurrentView() {
    this.switchView(this.currentView);
    this.refreshGlobalStats();
  },

  async loadGraphData(queryParams = "") {
    try {
      const res = await fetch(`/api/graph${queryParams ? `?${queryParams}` : ''}`, {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      
      if (this.graphViz) {
        this.graphViz.setData(data.nodes || [], data.edges || []);
      }

      this.populatePathSelects(data.nodes || []);
      this.updateMetrics(data.total_nodes, data.total_edges);
    } catch (e) {
      console.error("Load graph error:", e);
    }
  },

  async refreshGlobalStats() {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      this.updateMetrics(data.total_nodes, data.total_edges);

      // Fetch jurisdiction alerts count
      const jRes = await fetch("/api/jurisdictions/cross-links", { headers: window.Auth?.getAuthHeader() });
      const jData = await jRes.json();
      const badge = document.getElementById("navAlertsCount");
      if (badge) badge.textContent = jData.total_cross_jurisdictional_entities || 0;
    } catch (e) {
      console.error("Global stats error:", e);
    }
  },

  updateMetrics(nodesCount, edgesCount) {
    const nodeBadge = document.getElementById("metricTotalNodes");
    const edgeBadge = document.getElementById("metricTotalEdges");
    if (nodeBadge) nodeBadge.textContent = `${nodesCount || 0} Nodes`;
    if (edgeBadge) edgeBadge.textContent = `${edgesCount || 0} Edges`;
  },

  populatePathSelects(nodes) {
    const srcSelect = document.getElementById("pathSourceSelect");
    const dstSelect = document.getElementById("pathTargetSelect");
    if (!srcSelect || !dstSelect) return;

    const personNodes = nodes.filter(n => n.label === "Person");
    const options = personNodes.map(p => 
      `<option value="${p.id}">${p.name} (${p.operational_role || 'Suspect'})</option>`
    ).join("");

    srcSelect.innerHTML = `<option value="">-- Select Suspect A --</option>` + options;
    dstSelect.innerHTML = `<option value="">-- Select Suspect B --</option>` + options;
  },

  setupGraphFilters() {
    const labelFilter = document.getElementById("filterNodeType");
    const categoryFilter = document.getElementById("filterCrimeCategory");
    const clusterToggle = document.getElementById("btnToggleClusterColor");

    if (labelFilter) {
      labelFilter.addEventListener("change", () => this.applyFilters());
    }
    if (categoryFilter) {
      categoryFilter.addEventListener("change", () => this.applyFilters());
    }
    if (clusterToggle) {
      clusterToggle.addEventListener("click", () => {
        this.graphViz?.toggleCommunityColoring();
        const isCluster = this.graphViz?.colorByCommunity;
        clusterToggle.classList.toggle("btn-primary", isCluster);
        clusterToggle.classList.toggle("btn-secondary", !isCluster);
        this.showToast(isCluster ? "Community Gang Clusters Colored" : "Standard Risk Coloring Active", "info");
      });
    }
  },

  applyFilters() {
    const label = document.getElementById("filterNodeType")?.value || "";
    const cat = document.getElementById("filterCrimeCategory")?.value || "";
    const params = new URLSearchParams();
    if (label) params.set("label", label);
    if (cat) params.set("category", cat);
    this.loadGraphData(params.toString());
  },

  setupGlobalSearch() {
    const searchInput = document.getElementById("globalSearchInput");
    if (!searchInput) return;

    let debounce = null;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(debounce);
      const q = e.target.value.trim();
      if (!q) return;

      debounce = setTimeout(async () => {
        try {
          const res = await fetch(`/api/graph/search?q=${encodeURIComponent(q)}`, {
            headers: window.Auth?.getAuthHeader()
          });
          const data = await res.json();
          const results = data.results || [];
          if (results.length > 0) {
            const firstMatch = results[0];
            this.switchView("graph");
            this.graphViz?.centerOnNode(firstMatch.id);
            this.onNodeSelected(firstMatch);
            this.showToast(`Found: ${firstMatch.name} (${firstMatch.label})`, "success");
          } else {
            this.showToast("No matching entities found in network", "info");
          }
        } catch (err) {
          console.error("Search error:", err);
        }
      }, 400);
    });
  },

  onNodeSelected(node) {
    const panel = document.getElementById("graphInspectorPanel");
    if (!panel) return;

    const riskScore = node.risk_score || 0;
    const riskTier = node.risk_tier ? node.risk_tier.toLowerCase() : "low";

    panel.innerHTML = `
      <div style="border-bottom:1px solid var(--border-subtle); padding-bottom:10px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="role-badge">${node.label}</span>
          ${node.label === 'Person' ? `<span class="badge-risk ${riskTier}">Risk: ${riskScore}</span>` : ''}
        </div>
        <div style="font-size:16px; font-weight:700; color:var(--text-main); margin-top:6px;">
          ${node.name}
        </div>
        ${node.aliases?.length ? `<div style="font-size:11px; color:var(--text-muted);">@ ${node.aliases.join(", ")}</div>` : ''}
      </div>

      <div style="font-size:12px; display:flex; flex-direction:column; gap:8px;">
        ${node.operational_role ? `<div>Role: <strong>${node.operational_role}</strong></div>` : ''}
        ${node.phone ? `<div>Phone: <strong>${node.phone}</strong></div>` : ''}
        ${node.registration_number ? `<div>Vehicle Plate: <strong>${node.registration_number}</strong></div>` : ''}
        ${node.station ? `<div>Police Station: <strong>${node.station}</strong></div>` : ''}
        ${node.crime_category ? `<div>Crime Category: <strong>${node.crime_category}</strong></div>` : ''}
        ${node.community_name ? `<div>Syndicate Cluster: <strong>${node.community_name}</strong></div>` : ''}
      </div>

      <div style="margin-top:auto; display:flex; flex-direction:column; gap:8px;">
        <button class="btn btn-primary" style="width:100%; justify-content:center;" onclick="window.SuspectDossier?.openDossier('${node.id}')">
          🔍 Full 360° Dossier
        </button>
        <button class="btn btn-secondary" style="width:100%; justify-content:center;" onclick="window.App?.isolateEgoNetwork('${node.id}')">
          🌐 2-Hop Ego Network
        </button>
      </div>
    `;
  },

  async isolateEgoNetwork(nodeId) {
    try {
      const res = await fetch(`/api/graph/ego/${nodeId}?radius=2`, {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      if (this.graphViz) {
        this.graphViz.setData(data.nodes || [], data.edges || []);
        this.graphViz.centerOnNode(nodeId);
      }
      this.showToast(`Isolated 2-Hop Ego Network for ${nodeId} (${data.node_count} nodes)`, "info");
    } catch (e) {
      console.error("Ego network error:", e);
    }
  },

  setupResetButton() {
    const btn = document.getElementById("btnResetSynthetic");
    if (!btn) return;

    btn.addEventListener("click", async () => {
      if (confirm("Reset and re-seed all 3 MHA Synthetic Crime Syndicates?")) {
        try {
          const res = await fetch("/api/cases/synthetic/reset", {
            method: "POST",
            headers: window.Auth?.getAuthHeader()
          });
          const data = await res.json();
          this.showToast(data.message, "success");
          await this.loadGraphData();
          this.refreshCurrentView();
        } catch (e) {
          console.error("Reset error:", e);
        }
      }
    });
  },

  showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
};

window.App = App;
document.addEventListener("DOMContentLoaded", () => App.init());
