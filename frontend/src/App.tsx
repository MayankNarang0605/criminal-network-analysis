import React, { useState, useEffect } from 'react'
import Sidebar, { NavView } from './components/Sidebar'
import TopBar from './components/TopBar'
import CasesView from './components/CasesView'
import NetworkView from './components/NetworkView'
import FinancialView from './components/FinancialView'
import CDRView from './components/CDRView'
import AnomaliesView from './components/AnomaliesView'
import DossiersView from './components/DossiersView'
import ReportsView from './components/ReportsView'
import FIRView from './components/FIRView'
import AuditView from './components/AuditView'
import {
  FolderKanban, Users, Network, AlertTriangle, Shield,
  Activity, Database, Terminal, ArrowUpRight, CheckCircle2,
  FileSpreadsheet, ShieldAlert, Cpu, Layers, HardDrive
} from 'lucide-react'

interface SystemHealth {
  status: string
  services?: {
    neo4j?: { status: string; gds?: boolean; address?: string }
    postgres?: { status: string }
    gemini?: { status: string; model?: string }
  }
}

export default function App() {
  const [currentView, setCurrentView] = useState<NavView>('overview')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [stats, setStats] = useState({
    totalCases: 100,
    totalPersons: 1000,
    totalRelationships: 3412,
    activeAnomalies: 42,
    solvedCases: 0,
    datasetTier: 'Full 100-Case Multi-Tier',
  })

  // Poll system health
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch('/api/health')
        if (res.ok) {
          const data = await res.json()
          setHealth(data)
        } else {
          setHealth({ status: 'unhealthy' })
        }
      } catch {
        setHealth({ status: 'unhealthy' })
      }
    }

    fetchHealth()
    const interval = setInterval(fetchHealth, 15000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
      <Sidebar
        view={currentView}
        onNavigate={(v) => {
          setCurrentView(v)
          setSidebarOpen(false)
        }}
        isOpen={sidebarOpen}
      />

      {/* Main Content Area */}
      <div className="main-content main-area">
        <TopBar
          view={currentView}
          health={health}
          onMenuToggle={() => setSidebarOpen(!sidebarOpen)}
        />

        <main className="content-body content-area">

          {currentView === 'overview' && (
            <OverviewPanel stats={stats} health={health} onNavigate={setCurrentView} />
          )}

          {currentView === 'cases' && <CasesView />}
          {currentView === 'fir' && <FIRView />}
          {currentView === 'network' && <NetworkView />}
          {currentView === 'financial' && <FinancialView />}
          {currentView === 'cdr' && <CDRView />}
          {currentView === 'anomalies' && <AnomaliesView onNavigate={setCurrentView} />}
          {currentView === 'dossiers' && <DossiersView />}
          {currentView === 'reports' && <ReportsView />}
          {currentView === 'audit' && <AuditView />}
        </main>
      </div>
    </div>
  )
}

function OverviewPanel({
  stats,
  health,
  onNavigate,
}: {
  stats: any
  health: SystemHealth | null
  onNavigate: (v: NavView) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Top Banner / Mission Readiness */}
      <div className="glass-panel" style={{ padding: '20px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <Shield size={20} color="var(--accent)" />
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
              CrimeNet Command Center
            </h2>
            <span className="badge badge-accent">Strict Evidence Grounding</span>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
            Decision-support intelligence engine operating over 100 cases, synthetic Indian-context evidence graph, and cryptographic verification chains.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button
            className="btn btn-primary"
            id="quick-cases-btn"
            onClick={() => onNavigate('cases')}
          >
            <FolderKanban size={14} />
            Inspect Cases
          </button>
          <button
            className="btn btn-secondary"
            id="quick-network-btn"
            onClick={() => onNavigate('network')}
          >
            <Network size={14} />
            Graph Canvas
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        <div className="stat-card" style={{ cursor: 'pointer' }} onClick={() => onNavigate('cases')}>
          <div className="stat-label">Total Active Cases</div>
          <div className="stat-value">{stats.totalCases}</div>
          <div className="stat-footer" style={{ color: 'var(--info)' }}>
            <FolderKanban size={12} style={{ display: 'inline', marginRight: 4 }} />
            100 Cases / 4 Tiers
          </div>
        </div>

        <div className="stat-card" style={{ cursor: 'pointer' }} onClick={() => onNavigate('dossiers')}>
          <div className="stat-label">Resolved Entities</div>
          <div className="stat-value">{stats.totalPersons}</div>
          <div className="stat-footer" style={{ color: 'var(--accent)' }}>
            <Users size={12} style={{ display: 'inline', marginRight: 4 }} />
            Normalized Suspect Nodes
          </div>
        </div>

        <div className="stat-card" style={{ cursor: 'pointer' }} onClick={() => onNavigate('network')}>
          <div className="stat-label">Graph Relationships</div>
          <div className="stat-value">{stats.totalRelationships}</div>
          <div className="stat-footer" style={{ color: 'var(--success)' }}>
            <Network size={12} style={{ display: 'inline', marginRight: 4 }} />
            Calls, Transactions, Co-Travel
          </div>
        </div>

        <div className="stat-card" style={{ cursor: 'pointer' }} onClick={() => onNavigate('anomalies')}>
          <div className="stat-label">Flagged Anomalies</div>
          <div className="stat-value" style={{ color: 'var(--warning)' }}>{stats.activeAnomalies}</div>
          <div className="stat-footer" style={{ color: 'var(--warning)' }}>
            <AlertTriangle size={12} style={{ display: 'inline', marginRight: 4 }} />
            Layering & Burner Outliers
          </div>
        </div>
      </div>

      {/* System Status and Architecture Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        {/* Core Architecture Matrix */}
        <div className="glass-panel" style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Layers size={16} color="var(--accent)" />
              Dataset & Subsystem Pipeline
            </h3>
            <span className="badge badge-default">Section 6 Contract</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <PipelineRow
              phase="01"
              title="System of Record (PostgreSQL)"
              status="Online"
              desc="21 evidence tables, tamper-evident hash chains, audit logs"
              badge="Postgres 15"
            />
            <PipelineRow
              phase="02"
              title="Graph Topology (Neo4j & GDS)"
              status={health?.services?.neo4j?.status === 'healthy' ? 'Online' : 'Pending'}
              desc="Person, Case, Phone, Account, Vehicle, Organization nodes & relationships"
              badge="Bolt 7687"
            />
            <PipelineRow
              phase="03"
              title="Deterministic Analytics & Detectors"
              status="Ready"
              desc="10 core detectors, 13 financial/behavioral typologies, kingpin scoring"
              badge="Deterministic"
            />
            <PipelineRow
              phase="04"
              title="Evidence-Grounded AI Copilot"
              status={health?.services?.gemini?.status === 'configured' ? 'Configured' : 'Fallback Active'}
              desc="Explainable summaries strictly citing transaction, CDR, and case IDs"
              badge="Dual-Engine"
            />
          </div>
        </div>

        {/* Live Service Health */}
        <div className="glass-panel" style={{ padding: 20 }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 600, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Cpu size={16} color="var(--accent)" />
            Service Diagnostic
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <ServiceStatusItem
              name="PostgreSQL 15"
              desc="Evidence DB & Audit"
              isHealthy={health?.services?.postgres?.status === 'healthy'}
            />
            <ServiceStatusItem
              name="Neo4j Graph Database"
              desc="Graph analytics & GDS"
              isHealthy={health?.services?.neo4j?.status === 'healthy'}
            />
            <ServiceStatusItem
              name="FastAPI Backend"
              desc="Port 8000 (API Layer)"
              isHealthy={health?.status === 'healthy' || health?.status === 'degraded'}
            />
            <ServiceStatusItem
              name="Gemini LLM Provider"
              desc="Copilot natural language"
              isHealthy={health?.services?.gemini?.status === 'configured'}
              optionalNotice="Fallback mode enabled if off"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function PipelineRow({ phase, title, status, desc, badge }: { phase: string; title: string; status: string; desc: string; badge: string }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '10px 14px',
      background: 'rgba(255, 255, 255, 0.02)',
      borderRadius: 6,
      border: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--accent)', fontWeight: 700 }}>
          {phase}
        </span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{title}</div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{desc}</div>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="badge badge-default">{badge}</span>
        <span style={{ fontSize: 12, color: status === 'Online' || status === 'Ready' ? 'var(--success)' : 'var(--text-muted)' }}>
          {status}
        </span>
      </div>
    </div>
  )
}

function ServiceStatusItem({ name, desc, isHealthy, optionalNotice }: { name: string; desc: string; isHealthy: boolean; optionalNotice?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{name}</div>
        <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{desc}</div>
        {optionalNotice && !isHealthy && (
          <div style={{ fontSize: 10, color: 'var(--warning)', marginTop: 2 }}>{optionalNotice}</div>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span className={`status-dot ${isHealthy ? 'healthy' : 'unhealthy'}`} />
        <span style={{ fontSize: 12, color: isHealthy ? 'var(--success)' : 'var(--danger)' }}>
          {isHealthy ? 'Connected' : 'Offline'}
        </span>
      </div>
    </div>
  )
}
