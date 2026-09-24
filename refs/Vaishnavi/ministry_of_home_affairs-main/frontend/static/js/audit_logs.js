/**
 * Tamper-Evident Hash-Chained Audit Trail & Compliance Verification
 */

const AuditLogs = {
  async init() {
    await this.loadLogs();
    this.setupVerifyButton();
  },

  async loadLogs() {
    const tbody = document.getElementById("auditLogsTableBody");
    if (!tbody) return;

    try {
      const res = await fetch("/api/audit/logs?limit=40", {
        headers: window.Auth?.getAuthHeader()
      });
      const data = await res.json();
      const logs = data.logs || [];

      if (logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px;">No audit records found.</td></tr>`;
        return;
      }

      tbody.innerHTML = logs.map(l => `
        <tr>
          <td style="font-family:var(--font-mono); font-weight:700; color:var(--accent-blue);">#${l.sequence_id}</td>
          <td style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${l.timestamp?.replace('T', ' ').slice(0, 19)}</td>
          <td>
            <strong>${l.username}</strong>
            <div style="font-size:10px; color:var(--text-dim);">${l.user_role}</div>
          </td>
          <td>
            <span class="role-badge" style="font-size:10px;">${l.action}</span>
          </td>
          <td style="font-size:12px;">
            ${l.entity_type ? `${l.entity_type}: <strong>${l.entity_id || ''}</strong>` : '—'}
          </td>
          <td style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted);" title="${l.prev_hash}">
            ${l.prev_hash?.slice(0, 10)}...
          </td>
          <td style="font-family:var(--font-mono); font-size:10px; color:var(--accent-emerald);" title="${l.current_hash}">
            ${l.current_hash?.slice(0, 10)}...
          </td>
        </tr>
      `).join("");
    } catch (e) {
      console.error("Audit log error:", e);
    }
  },

  setupVerifyButton() {
    const btn = document.getElementById("btnVerifyChain");
    if (!btn) return;

    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.innerHTML = `⏳ Verifying SHA-256 Chain...`;

      try {
        const res = await fetch("/api/audit/verify-chain", {
          headers: window.Auth?.getAuthHeader()
        });
        const data = await res.json();
        const badge = document.getElementById("chainStatusBadge");

        if (data.valid) {
          if (badge) {
            badge.innerHTML = `
              <div class="toast success" style="position:static; width:100%;">
                🛡️ <strong>Chain Intact:</strong> ${data.message} (${data.total_records} Verified Blocks)
              </div>
            `;
          }
          window.App?.showToast("Cryptographic Audit Chain 100% verified!", "success");
        } else {
          if (badge) {
            badge.innerHTML = `
              <div class="toast error" style="position:static; width:100%;">
                ⚠️ <strong>TAMPER DETECTED:</strong> ${data.reason}
              </div>
            `;
          }
          window.App?.showToast("Audit chain failed integrity check!", "error");
        }
      } catch (e) {
        console.error("Verify chain error:", e);
      } finally {
        btn.disabled = false;
        btn.innerHTML = `🛡️ Run Cryptographic Verification`;
      }
    });
  }
};

window.AuditLogs = AuditLogs;
