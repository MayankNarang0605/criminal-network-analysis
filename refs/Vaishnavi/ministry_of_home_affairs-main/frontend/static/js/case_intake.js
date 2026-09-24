/**
 * Case Intake Studio & Real-Time NLP Entity Extraction Workbench
 */

const CaseIntake = {
  debounceTimer: null,

  // Curated Law Enforcement Demonstration Presets
  presets: {
    cyber: {
      fir_number: "512/2026",
      station: "Cyber Crime Police Station Rohini",
      state: "Delhi",
      jurisdiction_code: "DL-POLICE-SPL",
      crime_category: "Cyber Fraud & Phishing",
      investigating_officer: "Insp. Rajesh Kumar",
      narrative_text: "Complainant was deceived into transferring ₹85,00,000 across multiple mule bank accounts through a counterfeit stock trading application. Primary organizer identified as Mohammed Farhan @ Doctor operating from Nuh with burner phone 9810188234 and accomplice Aftab Alam. Fraud proceeds were routed to HDFC Mule Current Account A/c 50200088192341 and UPI farhan.mewat@okhdfcbank. Suspect was observed using white Hyundai Creta vehicle registration HR 26 BC 9988."
    },
    hawala: {
      fir_number: "94/2026",
      station: "Special Cell Lodhi Colony",
      state: "Delhi",
      jurisdiction_code: "DL-POLICE-SPL",
      crime_category: "Hawala & Terror Financing",
      investigating_officer: "ACP Vikramjit Singh",
      narrative_text: "Confidential intelligence led to interception of Angadia cash courier Jayesh Patel in central market. Recovered ₹1.8 Crore cash linked to hawala mastermind Haji Tariq Merchant @ Bhaijaan communicating on phone 9820199182. Transactions layered through Al-Barakah Bullion & Gems Trading and escrow ICICI account A/c 001105008812."
    },
    vehicle: {
      fir_number: "289/2026",
      station: "Sector 20 Police Station Noida",
      state: "Uttar Pradesh",
      jurisdiction_code: "UP-STF",
      crime_category: "Interstate Vehicle Theft",
      investigating_officer: "Insp. Manoj Tomar",
      narrative_text: "Interstate gang specializing in luxury SUV lifting cracked by special task force. Gang leader Satish Gujjar @ Pehalwan and chassis forger Vikas Tyagi apprehended. Recovered stolen Toyota Fortuner vehicle DL 01 AB 8844 with tampered engine number and forged registration documents. Contact recorded with phone 9811099281."
    }
  },

  init() {
    this.setupEventListeners();
    this.populateJurisdictions();
  },

  setupEventListeners() {
    const narrativeInput = document.getElementById("caseNarrativeInput");
    if (narrativeInput) {
      narrativeInput.addEventListener("input", () => {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => this.previewExtraction(), 350);
      });
    }

    const intakeForm = document.getElementById("caseIntakeForm");
    if (intakeForm) {
      intakeForm.addEventListener("submit", (e) => this.handleSubmit(e));
    }

    // Preset Buttons
    document.querySelectorAll(".btn-load-preset").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const presetKey = e.currentTarget.dataset.preset;
        this.loadPreset(presetKey);
      });
    });
  },

  async populateJurisdictions() {
    const select = document.getElementById("caseJurisdictionSelect");
    if (!select) return;
    try {
      const res = await fetch("/api/jurisdictions");
      const data = await res.json();
      select.innerHTML = data.jurisdictions.map(j => 
        `<option value="${j.code}">${j.name} (${j.state})</option>`
      ).join("");
    } catch (e) {
      console.error("Jurisdiction fetch error:", e);
    }
  },

  loadPreset(key) {
    const preset = this.presets[key];
    if (!preset) return;

    document.getElementById("caseFirNumber").value = preset.fir_number;
    document.getElementById("caseStation").value = preset.station;
    document.getElementById("caseState").value = preset.state;
    document.getElementById("caseCategorySelect").value = preset.crime_category;
    document.getElementById("caseIO").value = preset.investigating_officer;
    document.getElementById("caseNarrativeInput").value = preset.narrative_text;

    const jurSelect = document.getElementById("caseJurisdictionSelect");
    if (jurSelect) jurSelect.value = preset.jurisdiction_code;

    this.previewExtraction();
    window.App?.showToast(`Loaded preset scenario: ${preset.crime_category}`, "info");
  },

  async previewExtraction() {
    const text = document.getElementById("caseNarrativeInput")?.value?.trim();
    const previewContainer = document.getElementById("nlpEntityPreview");
    const categoryPredictor = document.getElementById("nlpCategoryPrediction");

    if (!text || text.length < 15) {
      if (previewContainer) previewContainer.innerHTML = `<span class="text-dim">Paste or type FIR narrative to see real-time AI entity recognition tags...</span>`;
      return;
    }

    try {
      const res = await fetch("/api/cases/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...window.Auth?.getAuthHeader() },
        body: JSON.stringify({ narrative_text: text })
      });
      const data = await res.json();
      const ext = data.extracted_entities || {};
      const cls = data.classification || {};

      // Render Predicted Category & Confidence
      if (categoryPredictor && cls.predicted_category) {
        categoryPredictor.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-weight:600; color:var(--accent-blue);">AI Predicted Category: ${cls.predicted_category}</span>
            <span class="badge-risk medium">${cls.confidence_percentage}% Confidence</span>
          </div>
          <div style="font-size:11px; color:var(--text-muted);">
            Applicable Sections: ${cls.applicable_legal_sections?.join(", ") || "General IPC"}
          </div>
        `;
      }

      // Render Entity Badges
      let tagsHtml = "";
      (ext.persons || []).forEach(p => {
        tagsHtml += `<span class="tag-badge tag-person">👤 Suspect: ${p.name} ${p.aliases?.length ? `(@ ${p.aliases.join(', ')})` : ''}</span>`;
      });
      (ext.phones || []).forEach(ph => {
        tagsHtml += `<span class="tag-badge tag-phone">📞 Phone: ${ph.masked}</span>`;
      });
      (ext.vehicles || []).forEach(v => {
        tagsHtml += `<span class="tag-badge tag-vehicle">🚗 Vehicle: ${v.registration_number}</span>`;
      });
      (ext.financial_accounts || []).forEach(acc => {
        tagsHtml += `<span class="tag-badge tag-account">💳 ${acc.type}: ${acc.masked}</span>`;
      });
      (ext.organizations || []).forEach(org => {
        tagsHtml += `<span class="tag-badge tag-org">🏢 Org: ${org.name}</span>`;
      });
      (ext.locations || []).forEach(loc => {
        tagsHtml += `<span class="tag-badge tag-location">📍 Location: ${loc.name}</span>`;
      });

      if (previewContainer) {
        previewContainer.innerHTML = tagsHtml || `<span class="text-dim">No high-confidence entities recognized yet. Keep typing...</span>`;
      }
    } catch (e) {
      console.error("Preview error:", e);
    }
  },

  async handleSubmit(e) {
    e.preventDefault();
    const firNumber = document.getElementById("caseFirNumber").value.trim();
    const station = document.getElementById("caseStation").value.trim();
    const state = document.getElementById("caseState").value.trim();
    const jurisdiction = document.getElementById("caseJurisdictionSelect").value;
    const category = document.getElementById("caseCategorySelect").value;
    const io = document.getElementById("caseIO").value.trim();
    const narrative = document.getElementById("caseNarrativeInput").value.trim();

    if (!firNumber || !station || !narrative) {
      window.App?.showToast("FIR Number, Station, and Narrative are required", "error");
      return;
    }

    try {
      const res = await fetch("/api/cases/intake", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...window.Auth?.getAuthHeader() },
        body: JSON.stringify({
          fir_number: firNumber,
          station: station,
          state: state,
          jurisdiction_code: jurisdiction,
          crime_category: category,
          investigating_officer: io,
          narrative_text: narrative
        })
      });
      const data = await res.json();
      if (res.ok) {
        window.App?.showToast(data.message, "success");
        // Reset form
        document.getElementById("caseIntakeForm").reset();
        document.getElementById("nlpEntityPreview").innerHTML = "";
        // Switch to Graph Explorer view to inspect newly created nodes
        window.App?.switchView("graph");
        window.App?.loadGraphData();
      } else {
        window.App?.showToast(data.error || "Case intake failed", "error");
      }
    } catch (err) {
      console.error("Intake submit error:", err);
      window.App?.showToast("Submission failed", "error");
    }
  }
};

window.CaseIntake = CaseIntake;
