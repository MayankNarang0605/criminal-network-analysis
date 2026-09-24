/**
 * Authentication and Role-Based Access Control (RBAC) Client Handler
 */

const Auth = {
  currentUser: null,
  token: localStorage.getItem("mha_auth_token") || null,

  async init() {
    this.setupRoleSelector();
    if (this.token) {
      await this.fetchCurrentUser();
    } else {
      // Auto-login as default Investigating Officer for frictionless demo
      await this.login("io_rajesh", "iopassword");
    }
  },

  getAuthHeader() {
    return this.token ? { "Authorization": `Bearer ${this.token}` } : {};
  },

  async login(username, password) {
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      const data = await response.json();
      if (response.ok) {
        this.token = data.access_token;
        this.currentUser = data.user;
        localStorage.setItem("mha_auth_token", this.token);
        this.updateUI();
        window.App?.showToast(`Logged in as ${data.user.full_name} (${data.user.role})`, "success");
        return true;
      } else {
        window.App?.showToast(data.error || "Login failed", "error");
        return false;
      }
    } catch (e) {
      console.error("Auth error:", e);
      return false;
    }
  },

  async fetchCurrentUser() {
    try {
      const response = await fetch("/api/auth/me", {
        headers: this.getAuthHeader()
      });
      if (response.ok) {
        const data = await response.json();
        this.currentUser = data.user;
        this.updateUI();
      } else {
        // Token invalid, login as default
        await this.login("io_rajesh", "iopassword");
      }
    } catch (e) {
      console.error("Fetch user error:", e);
    }
  },

  setupRoleSelector() {
    const roleSelect = document.getElementById("headerRoleSelect");
    if (!roleSelect) return;

    roleSelect.addEventListener("change", async (e) => {
      const selectedUser = e.target.value;
      const passMap = {
        "admin": "adminpassword",
        "io_rajesh": "iopassword",
        "analyst_priya": "analystpassword",
        "auditor_verma": "auditorpassword"
      };
      await this.login(selectedUser, passMap[selectedUser] || "password");
      window.App?.refreshCurrentView();
    });
  },

  updateUI() {
    if (!this.currentUser) return;

    const roleBadge = document.getElementById("headerRoleBadge");
    const officerName = document.getElementById("headerOfficerName");
    const roleSelect = document.getElementById("headerRoleSelect");

    if (roleBadge) {
      roleBadge.textContent = this.currentUser.role;
      roleBadge.className = `role-badge ${this.currentUser.role.toLowerCase().replace(/ /g, '-')}`;
    }
    if (officerName) {
      officerName.textContent = this.currentUser.full_name;
    }
    if (roleSelect && roleSelect.value !== this.currentUser.username) {
      roleSelect.value = this.currentUser.username;
    }
  },

  hasRole(roleName) {
    return this.currentUser && this.currentUser.role.toLowerCase() === roleName.toLowerCase();
  }
};

window.Auth = Auth;
