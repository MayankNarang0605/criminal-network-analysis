import {
  LayoutDashboard, FolderKanban, FileText, Network, CreditCard,
  Phone, Users, BarChart3,
  ShieldCheck, Settings, ChevronRight, Shield
} from 'lucide-react'

export type NavView =
  | 'overview' | 'cases' | 'fir' | 'network' | 'financial'
  | 'cdr' | 'anomalies'
  | 'dossiers' | 'reports' | 'audit'

export interface NavItem {
  id: NavView
  label: string
  icon: React.ElementType
  section: string
  badge?: { text: string; type: 'danger' | 'info' }
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'overview',      label: 'Command Center',      icon: LayoutDashboard, section: 'Core' },
  { id: 'cases',         label: 'Cases',               icon: FolderKanban,   section: 'Core' },
  { id: 'fir',           label: 'FIR Intelligence',    icon: FileText,        section: 'Intelligence' },
  { id: 'network',       label: 'Network Analysis',    icon: Network,         section: 'Intelligence' },
  { id: 'financial',     label: 'Financial',           icon: CreditCard,      section: 'Intelligence' },
  { id: 'cdr',           label: 'CDR Analysis',        icon: Phone,           section: 'Intelligence' },
  { id: 'anomalies',     label: 'Anomalies',           icon: BarChart3,       section: 'Analysis' },
  { id: 'dossiers',      label: 'Suspect Dossiers',    icon: Users,           section: 'Analysis' },
  { id: 'reports',       label: 'Reports',             icon: ShieldCheck,     section: 'Integrity' },
  { id: 'audit',         label: 'Audit Trail',         icon: Settings,        section: 'Integrity' },
]

const SECTIONS = ['Core', 'Intelligence', 'Analysis', 'Integrity']

interface SidebarProps {
  view: NavView
  onNavigate: (v: NavView) => void
  isOpen: boolean
}

export default function Sidebar({ view, onNavigate, isOpen }: SidebarProps) {
  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Shield size={16} color="#000" strokeWidth={2.5} />
        </div>
        <div>
          <div className="sidebar-logo-text">CrimeNet</div>
          <div className="sidebar-logo-sub">Network Analysis System</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {SECTIONS.map(section => (
          <div key={section}>
            <div className="sidebar-section">{section}</div>
            {NAV_ITEMS.filter(n => n.section === section).map(item => {
              const Icon = item.icon
              const isActive = view === item.id
              return (
                <button
                  key={item.id}
                  id={`nav-${item.id}`}
                  className={`nav-item ${isActive ? 'active' : ''}`}
                  onClick={() => onNavigate(item.id)}
                >
                  <Icon className="nav-icon" size={15} />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className={`nav-badge ${item.badge.type}`}>
                      {item.badge.text}
                    </span>
                  )}
                  {isActive && <ChevronRight size={12} style={{ marginLeft: 'auto', opacity: 0.5 }} />}
                </button>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: '10px', color: 'var(--text-faint)', lineHeight: 1.5 }}>
          <div style={{ fontWeight: 600, color: 'var(--text-dim)', marginBottom: 2 }}>
            Decision-support prototype
          </div>
          All findings require investigator review.
        </div>
      </div>
    </aside>
  )
}
