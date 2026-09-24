import { Search, Bell, Activity, Menu } from 'lucide-react'

interface SystemHealth {
  status: string
  services?: {
    neo4j?: { status: string }
    postgres?: { status: string }
  }
}

interface TopBarProps {
  view: string
  health: SystemHealth | null
  onMenuToggle: () => void
}

const VIEW_LABELS: Record<string, string> = {
  overview: 'Command Center',
  cases: 'Cases',
  fir: 'FIR Intelligence',
  network: 'Network Analysis',
  financial: 'Financial Intelligence',
  cdr: 'CDR Analysis',
  anomalies: 'Anomaly Detection',
  dossiers: 'Suspect Dossiers',
  reports: 'Reports',
  audit: 'Audit Trail',
}

function StatusIndicator({ health }: { health: SystemHealth | null }) {
  if (!health) return <span className="status-dot loading" title="Connecting..." />
  const s = health.status
  const cls = s === 'healthy' ? 'healthy' : s === 'degraded' ? 'degraded' : 'unhealthy'
  const label = s === 'healthy' ? 'All Systems Operational' : s === 'degraded' ? 'Degraded' : 'Offline'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span className={`status-dot ${cls}`} />
      <span style={{ fontSize: 12, color: 'var(--text-faint)', display: 'none' }}>
        {label}
      </span>
      <span style={{ fontSize: 12, color: 'var(--text-faint)' }}>{label}</span>
    </div>
  )
}

export default function TopBar({ view, health, onMenuToggle }: TopBarProps) {
  return (
    <header className="topbar">
      {/* Mobile menu toggle */}
      <button className="topbar-btn" id="menu-toggle" onClick={onMenuToggle}
        style={{ display: 'none' }}>
        <Menu size={16} />
      </button>

      {/* Page title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <Activity size={14} style={{ color: 'var(--accent)' }} />
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
          {VIEW_LABELS[view] ?? view}
        </span>
      </div>

      {/* Search */}
      <div className="topbar-search" style={{ marginLeft: 16 }}>
        <Search className="search-icon" />
        <input
          id="global-search"
          type="text"
          placeholder="Search persons, cases, vehicles, accounts…"
        />
      </div>

      <div className="topbar-spacer" />

      {/* Status */}
      <StatusIndicator health={health} />

      {/* Alerts */}
      <button className="topbar-btn" id="alerts-btn" title="Alerts">
        <Bell size={15} />
      </button>
    </header>
  )
}
