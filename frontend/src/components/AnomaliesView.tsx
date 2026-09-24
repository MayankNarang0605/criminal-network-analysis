// Anomaly Detection View — Prioritized Forensic Triage with Deep Investigation
import React, { useState, useEffect, useMemo } from 'react'
import {
  AlertTriangle, Filter, RefreshCw, Cpu, Database,
  ArrowRight, ShieldCheck, Search, Activity, ChevronRight,
  ExternalLink, Check, Copy, Sliders, Layers, Sparkles,
  CreditCard, Phone, MapPin, Eye, FileText, Network, Clock,
  ArrowDown, X, Compass, UserCheck, ShieldAlert
} from 'lucide-react'
import { NavView } from './Sidebar'

interface AnomalyGroup {
  group_id: string
  case_id: string
  detection_engine: 'ML' | 'RULE'
  anomaly_type: 'Financial' | 'CDR' | 'Geospatial' | string
  detector_name: string
  model_used: string
  title: string
  subtitle: string
  entity: string
  entity_id: string
  entity_type: string
  event_count: number
  primary_date: string
  what_happened: string
  when: string
  why_unusual: string
  why_unusual_detail?: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  anomaly_score_100: number
  deviation_multiplier: number
  evidence: string[]
  investigate_data: {
    counterparties?: Array<{
      account_id?: string
      contact?: string
      transaction_count?: number
      call_count?: number
      total_volume?: number
      formatted_volume?: string
      formatted_duration?: string
    }>
    evidence_records?: Array<{
      id: string
      type: string
      timestamp?: string
      date_formatted?: string
      amount?: number
      amount_formatted?: string
      duration_seconds?: number
      duration_formatted?: string
      city?: string
      location_name?: string
      coordinates?: string
      details?: string
      deviation?: string
    }>
    timeline?: Array<{
      timestamp?: string
      date?: string
      title: string
      description: string
      badge?: string
    }>
    location?: {
      core_anchor_city?: string
      cities_visited?: string[]
      total_distance_km?: number
      peak_velocity_kmh?: number
    }
    model_details?: Record<string, any>
    entity_profile?: Record<string, any>
    network?: {
      primary_node: string
      connections: Array<{
        target: string
        relationship: string
        volume?: string
        count?: number
      }>
    }
  }
}

interface AnomaliesApiResponse {
  case_id?: string | null
  total_detected: number
  total_anomalies: number
  critical_count: number
  high_count: number
  medium_count: number
  low_count: number
  financial_count: number
  cdr_count: number
  geospatial_count: number
  ml_count: number
  rule_count: number
  ml_anomalies: AnomalyGroup[]
  rule_anomalies: AnomalyGroup[]
  anomalies: AnomalyGroup[]
}

interface CaseOption {
  case_id: string
  title?: string
  crime_type?: string
}

interface AnomaliesViewProps {
  onNavigate?: (v: NavView) => void
}

const SEV_THEMES: Record<string, { ring: string; text: string; bg: string; dot: string }> = {
  CRITICAL: { ring: '#ef4444', text: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)', dot: '🔴' },
  HIGH: { ring: '#f59e0b', text: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)', dot: '🟠' },
  MEDIUM: { ring: '#00d2ff', text: '#00d2ff', bg: 'rgba(0, 210, 255, 0.12)', dot: '🔵' },
  LOW: { ring: '#10b981', text: '#10b981', bg: 'rgba(16, 185, 129, 0.12)', dot: '🟢' },
}

const TYPE_ICONS: Record<string, React.ElementType> = {
  Financial: CreditCard,
  CDR: Phone,
  Geospatial: MapPin,
}

export default function AnomaliesView({ onNavigate }: AnomaliesViewProps) {
  const [data, setData] = useState<AnomaliesApiResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Top Filter States
  const [caseList, setCaseList] = useState<CaseOption[]>([])
  const [selectedCase, setSelectedCase] = useState<string>('CASE001')
  const [engineTab, setEngineTab] = useState<'ML' | 'RULE' | 'ALL'>('ML')
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL')
  const [severityFilter, setSeverityFilter] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [showTopOnly, setShowTopOnly] = useState<boolean>(true)

  // Investigation Modal State
  const [investigatingAnomaly, setInvestigatingAnomaly] = useState<AnomalyGroup | null>(null)
  const [activeModalTab, setActiveModalTab] = useState<'evidence' | 'counterparties' | 'network' | 'location' | 'timeline' | 'entity' | 'model'>('evidence')
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Load cases dropdown
  useEffect(() => {
    fetch('/api/cases?limit=100')
      .then(res => res.json())
      .then(cases => {
        if (Array.isArray(cases)) {
          setCaseList(cases.map((c: any) => ({
            case_id: c.case_id,
            title: c.title,
            crime_type: c.crime_type,
          })))
        }
      })
      .catch(() => {})
  }, [])

  // Load anomalies
  const loadAnomalies = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (selectedCase && selectedCase !== 'ALL') {
        params.append('case_id', selectedCase)
      }
      if (categoryFilter !== 'ALL') {
        params.append('anomaly_type', categoryFilter)
      }
      if (severityFilter !== 'ALL') {
        params.append('severity', severityFilter)
      }
      if (engineTab !== 'ALL') {
        params.append('engine', engineTab)
      }
      params.append('limit', '250')

      const res = await fetch(`/api/analytics/anomalies?${params.toString()}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json: AnomaliesApiResponse = await res.json()
      setData(json)
    } catch (err: any) {
      setError(err.message || 'Failed to fetch anomaly records')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAnomalies()
  }, [selectedCase, engineTab, categoryFilter, severityFilter])

  // Filtered and Prioritized List
  const prioritizedList = useMemo(() => {
    if (!data?.anomalies) return []
    let list = data.anomalies

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      list = list.filter(item =>
        item.title.toLowerCase().includes(q) ||
        item.entity.toLowerCase().includes(q) ||
        item.what_happened.toLowerCase().includes(q) ||
        item.why_unusual.toLowerCase().includes(q) ||
        item.evidence.some(ev => ev.toLowerCase().includes(q))
      )
    }

    return showTopOnly ? list.slice(0, 10) : list
  }, [data, searchQuery, showTopOnly])

  const copyEvidence = (id: string) => {
    navigator.clipboard.writeText(id)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1800)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* ── 1. Top Triage Funnel Header (ANOMALY INTELLIGENCE) ─────────── */}
      <div className="glass-panel" style={{ padding: '20px 24px', background: 'linear-gradient(135deg, rgba(15,23,42,0.85) 0%, rgba(30,41,59,0.85) 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <ShieldAlert size={20} color="#ef4444" />
              <h2 style={{ fontSize: 18, fontWeight: 800, margin: 0, color: 'var(--text-bright)', letterSpacing: '0.04em' }}>
                ANOMALY INTELLIGENCE
              </h2>
              <span className="badge badge-danger" style={{ fontSize: 11, fontWeight: 700 }}>
                Prioritized Findings
              </span>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
              Identifies acute deviations that static rules miss. Showing prioritized meaningful findings grouped by entity.
            </p>
          </div>

          {/* Case Selector Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)' }}>Scope:</span>
            <select
              id="case-select-dropdown"
              value={selectedCase}
              onChange={e => setSelectedCase(e.target.value)}
              className="input-field"
              style={{ minWidth: 200, fontWeight: 600, background: 'rgba(15,23,42,0.9)' }}
            >
              <option value="ALL">🌐 All Cases (Cross-Case Syndicate)</option>
              <optgroup label="Specific Cases">
                {caseList.map(c => (
                  <option key={c.case_id} value={c.case_id}>
                    {c.case_id} {c.title ? `— ${c.title}` : ''}
                  </option>
                ))}
              </optgroup>
            </select>

            <button
              id="refresh-btn"
              className="btn btn-secondary"
              onClick={loadAnomalies}
              disabled={loading}
              title="Re-run Detection Pipelines"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>

        {/* ── Visual Triage Funnel Strip ─────────────────────────────────── */}
        <div style={{
          marginTop: 16,
          padding: '14px 18px',
          borderRadius: 8,
          background: 'rgba(0,0,0,0.35)',
          border: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 14,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-bright)', fontFamily: 'var(--mono)' }}>
                {loading ? '…' : data?.total_detected ?? 0}
              </span>
              <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 600 }}>detected</span>
            </div>

            <ArrowDown size={16} color="var(--text-faint)" />

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span
                onClick={() => setSeverityFilter(severityFilter === 'CRITICAL' ? 'ALL' : 'CRITICAL')}
                style={{
                  padding: '4px 10px',
                  borderRadius: 20,
                  background: 'rgba(239,68,68,0.15)',
                  border: severityFilter === 'CRITICAL' ? '1px solid #ef4444' : '1px solid rgba(239,68,68,0.3)',
                  color: '#ef4444',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                🔴 {data?.critical_count ?? 0} Critical
              </span>

              <span
                onClick={() => setSeverityFilter(severityFilter === 'HIGH' ? 'ALL' : 'HIGH')}
                style={{
                  padding: '4px 10px',
                  borderRadius: 20,
                  background: 'rgba(245,158,11,0.15)',
                  border: severityFilter === 'HIGH' ? '1px solid #f59e0b' : '1px solid rgba(245,158,11,0.3)',
                  color: '#f59e0b',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                🟠 {data?.high_count ?? 0} High
              </span>

              <span
                onClick={() => setSeverityFilter(severityFilter === 'MEDIUM' ? 'ALL' : 'MEDIUM')}
                style={{
                  padding: '4px 10px',
                  borderRadius: 20,
                  background: 'rgba(0,210,255,0.15)',
                  border: severityFilter === 'MEDIUM' ? '1px solid #00d2ff' : '1px solid rgba(0,210,255,0.3)',
                  color: '#00d2ff',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                🔵 {data?.medium_count ?? 0} Medium
              </span>

              <span
                onClick={() => setSeverityFilter(severityFilter === 'LOW' ? 'ALL' : 'LOW')}
                style={{
                  padding: '4px 10px',
                  borderRadius: 20,
                  background: 'rgba(16,185,129,0.15)',
                  border: severityFilter === 'LOW' ? '1px solid #10b981' : '1px solid rgba(16,185,129,0.3)',
                  color: '#10b981',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                🟢 {data?.low_count ?? 0} Low
              </span>
            </div>
          </div>

          {/* Toggle Button: [Show Top 10] vs [Show All] */}
          <button
            id="toggle-top-btn"
            className="btn btn-primary"
            style={{ padding: '6px 14px', fontSize: 12, fontWeight: 700 }}
            onClick={() => setShowTopOnly(!showTopOnly)}
          >
            {showTopOnly ? `Show Top 10 Priority` : `Showing All (${data?.total_anomalies ?? 0})`}
          </button>
        </div>
      </div>

      {/* ── 2. Layer Tabs: Keep ML & Rules Separated ─────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        {/* Primary Segmented Toggle */}
        <div style={{ display: 'flex', gap: 6, background: 'rgba(15,23,42,0.6)', padding: 4, borderRadius: 8, border: '1px solid var(--border)' }}>
          <button
            id="tab-engine-ml"
            className={`btn ${engineTab === 'ML' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ padding: '6px 14px', fontSize: 13, fontWeight: 700 }}
            onClick={() => setEngineTab('ML')}
          >
            🤖 ML & Statistical Detections ({data?.ml_count ?? 0})
          </button>

          <button
            id="tab-engine-rules"
            className={`btn ${engineTab === 'RULE' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ padding: '6px 14px', fontSize: 13, fontWeight: 700 }}
            onClick={() => setEngineTab('RULE')}
          >
            ⚖️ Rule-Based Detections ({data?.rule_count ?? 0})
          </button>

          <button
            id="tab-engine-all"
            className={`btn ${engineTab === 'ALL' ? 'btn-primary' : 'btn-ghost'}`}
            style={{ padding: '6px 12px', fontSize: 12, fontWeight: 600 }}
            onClick={() => setEngineTab('ALL')}
          >
            All Unified
          </button>
        </div>

        {/* Search Input */}
        <div style={{ position: 'relative', minWidth: 240 }}>
          <Search size={14} color="var(--text-faint)" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} />
          <input
            id="search-input"
            type="text"
            className="input-field"
            placeholder="Search finding, account, entity..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{ paddingLeft: 32, fontSize: 12, width: '100%' }}
          />
        </div>
      </div>

      {/* Category Filter Badges */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-faint)' }}>Category:</span>
        {[
          { id: 'ALL', label: 'All Categories' },
          { id: 'Financial', label: '💰 Financial' },
          { id: 'CDR', label: '📞 CDR Telecom' },
          { id: 'Geospatial', label: '📍 Geospatial' },
        ].map(cat => (
          <button
            key={cat.id}
            id={`filter-cat-${cat.id.toLowerCase()}`}
            className={`btn ${categoryFilter === cat.id ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '4px 10px', fontSize: 11, fontWeight: 600 }}
            onClick={() => setCategoryFilter(cat.id)}
          >
            {cat.label}
          </button>
        ))}

        {severityFilter !== 'ALL' && (
          <button
            className="btn btn-ghost"
            style={{ padding: '4px 8px', fontSize: 11, color: '#ef4444' }}
            onClick={() => setSeverityFilter('ALL')}
          >
            Clear Severity Filter ({severityFilter}) ✕
          </button>
        )}
      </div>

      {/* ── 3. Prioritized 4-Item Grouped Cards Grid ────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 14 }}>
        {loading ? (
          <div className="glass-panel" style={{ gridColumn: '1 / -1', padding: 48, textAlign: 'center', color: 'var(--text-dim)' }}>
            <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px', color: 'var(--accent)' }} />
            <div>Running ML Isolation Forest, LOF, and DBSCAN engines on evidence graph...</div>
          </div>
        ) : error ? (
          <div className="glass-panel" style={{ gridColumn: '1 / -1', padding: 32, textAlign: 'center', color: '#ef4444' }}>
            <AlertTriangle size={24} style={{ margin: '0 auto 12px' }} />
            <div>Error: {error}</div>
            <button className="btn btn-secondary" style={{ marginTop: 12 }} onClick={loadAnomalies}>Retry</button>
          </div>
        ) : prioritizedList.length === 0 ? (
          <div className="glass-panel" style={{ gridColumn: '1 / -1', padding: 48, textAlign: 'center', color: 'var(--text-faint)' }}>
            <Check size={28} style={{ margin: '0 auto 12px', color: '#10b981' }} />
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-bright)' }}>No Anomalies Found</div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
              No behavior matches current filters for {selectedCase === 'ALL' ? 'all cases' : selectedCase}.
            </p>
          </div>
        ) : (
          prioritizedList.map((anomaly, idx) => {
            const theme = SEV_THEMES[anomaly.severity] || SEV_THEMES.MEDIUM
            const TypeIcon = TYPE_ICONS[anomaly.anomaly_type] || AlertTriangle
            const isML = anomaly.detection_engine === 'ML'

            return (
              <div
                key={anomaly.group_id || idx}
                id={`card-${idx}`}
                className="glass-panel"
                style={{
                  padding: '18px 20px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: 14,
                  borderLeft: `4px solid ${theme.ring}`,
                  position: 'relative',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                  cursor: 'pointer',
                }}
                onClick={() => {
                  setInvestigatingAnomaly(anomaly)
                  setActiveModalTab('evidence')
                }}
              >
                {/* Header: Title + Severity & Score */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 13 }}>{theme.dot}</span>
                      <span style={{
                        fontSize: 11,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: theme.text,
                        fontWeight: 800,
                      }}>
                        {anomaly.anomaly_type.toUpperCase()} SPIKE
                      </span>
                      <span style={{
                        fontSize: 10,
                        padding: '1px 6px',
                        borderRadius: 4,
                        background: isML ? 'rgba(99,102,241,0.15)' : 'rgba(148,163,184,0.15)',
                        color: isML ? '#a5b4fc' : '#cbd5e1',
                        fontFamily: 'var(--mono)',
                        fontWeight: 600,
                      }}>
                        {isML ? 'ML Engine' : 'Regulatory Rule'}
                      </span>
                    </div>

                    {/* How severe is it? (Score /100) */}
                    <div style={{
                      padding: '3px 8px',
                      borderRadius: 14,
                      background: theme.bg,
                      border: `1px solid ${theme.ring}`,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      flexShrink: 0,
                    }}>
                      <span style={{ fontSize: 12, fontWeight: 800, color: theme.text, fontFamily: 'var(--mono)' }}>
                        Score: {anomaly.anomaly_score_100}
                      </span>
                      <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>/100</span>
                    </div>
                  </div>

                  {/* Subtitle / Grouping info */}
                  <h3 style={{ fontSize: 15, fontWeight: 700, margin: '2px 0 4px', color: 'var(--text-bright)' }}>
                    {anomaly.title}
                  </h3>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                    {anomaly.event_count} related events • {anomaly.when}
                  </div>
                </div>

                {/* ── 4 Cardinal Answers ───────────────────────────────── */}
                <div style={{
                  padding: '12px 14px',
                  borderRadius: 8,
                  background: 'rgba(0,0,0,0.25)',
                  border: '1px solid rgba(255,255,255,0.05)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}>
                  {/* 1. What happened? */}
                  <div>
                    <span style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-faint)', fontWeight: 700, letterSpacing: '0.04em' }}>
                      What Happened?
                    </span>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>
                      {anomaly.what_happened}
                    </div>
                  </div>

                  {/* 2. Why is it unusual? */}
                  <div>
                    <span style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-faint)', fontWeight: 700, letterSpacing: '0.04em' }}>
                      Why Unusual?
                    </span>
                    <div style={{ fontSize: 12, fontWeight: 600, color: theme.text, marginTop: 1 }}>
                      {anomaly.why_unusual}
                    </div>
                    {anomaly.why_unusual_detail && (
                      <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2, lineHeight: 1.4 }}>
                        {anomaly.why_unusual_detail}
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Action: [Investigate] Button */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 6 }}>
                  <span style={{ fontSize: 11, color: 'var(--text-faint)', fontFamily: 'var(--mono)' }}>
                    {anomaly.evidence.length} Evidence citations
                  </span>

                  <button
                    id={`investigate-btn-${idx}`}
                    className="btn btn-primary"
                    style={{ padding: '5px 14px', fontSize: 12, fontWeight: 700 }}
                    onClick={(e) => {
                      e.stopPropagation()
                      setInvestigatingAnomaly(anomaly)
                      setActiveModalTab('evidence')
                    }}
                  >
                    Investigate →
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* ── 4. Deep Investigation Modal (All details behind Investigate) ─── */}
      {investigatingAnomaly && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: 20,
          }}
          onClick={() => setInvestigatingAnomaly(null)}
        >
          <div
            className="glass-panel"
            style={{
              width: '100%',
              maxWidth: 900,
              maxHeight: '88vh',
              background: '#0f172a',
              border: '1px solid var(--border)',
              borderRadius: 12,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.7)',
            }}
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{
              padding: '18px 24px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'rgba(15, 23, 42, 0.9)',
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{
                    padding: '3px 8px',
                    borderRadius: 4,
                    background: SEV_THEMES[investigatingAnomaly.severity]?.bg,
                    color: SEV_THEMES[investigatingAnomaly.severity]?.text,
                    fontSize: 11,
                    fontWeight: 800,
                  }}>
                    {investigatingAnomaly.severity} OUTLIER
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--text-faint)', fontFamily: 'var(--mono)' }}>
                    Score {investigatingAnomaly.anomaly_score_100}/100 • {investigatingAnomaly.deviation_multiplier}× deviation
                  </span>
                </div>
                <h3 style={{ fontSize: 18, fontWeight: 800, margin: 0, color: 'var(--text-bright)' }}>
                  {investigatingAnomaly.title}
                </h3>
              </div>

              <button
                className="btn btn-ghost"
                style={{ padding: 6, borderRadius: '50%' }}
                onClick={() => setInvestigatingAnomaly(null)}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Navigation Tabs */}
            <div style={{
              display: 'flex',
              gap: 4,
              padding: '8px 20px',
              borderBottom: '1px solid var(--border)',
              background: 'rgba(0,0,0,0.2)',
              overflowX: 'auto',
            }}>
              {[
                { id: 'evidence', label: `Evidence (${investigatingAnomaly.evidence.length})`, icon: FileText },
                { id: 'counterparties', label: 'Counterparties', icon: Users },
                { id: 'network', label: 'Network', icon: Network },
                { id: 'location', label: 'Location & Transit', icon: MapPin },
                { id: 'timeline', label: 'Timeline', icon: Clock },
                { id: 'entity', label: 'Entity Dossier', icon: Eye },
                { id: 'model', label: 'Model Details', icon: Cpu },
              ].map(tab => {
                const Icon = tab.icon
                const active = activeModalTab === tab.id
                return (
                  <button
                    key={tab.id}
                    id={`modal-tab-${tab.id}`}
                    className={`btn ${active ? 'btn-primary' : 'btn-ghost'}`}
                    style={{ padding: '6px 12px', fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
                    onClick={() => setActiveModalTab(tab.id as any)}
                  >
                    <Icon size={14} />
                    {tab.label}
                  </button>
                )
              })}
            </div>

            {/* Modal Body Content */}
            <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* TAB 1: Evidence Records */}
              {activeModalTab === 'evidence' && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: 8 }}>
                    Concrete Evidentiary Records ({investigatingAnomaly.investigate_data.evidence_records?.length || 0})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {investigatingAnomaly.investigate_data.evidence_records?.map((rec, i) => (
                      <div
                        key={i}
                        style={{
                          padding: '10px 14px',
                          borderRadius: 6,
                          background: 'rgba(0,0,0,0.3)',
                          border: '1px solid rgba(255,255,255,0.06)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: 12,
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <button
                              onClick={() => copyEvidence(rec.id)}
                              style={{
                                padding: '2px 8px',
                                borderRadius: 4,
                                background: 'rgba(0, 210, 255, 0.08)',
                                border: '1px solid rgba(0, 210, 255, 0.2)',
                                color: 'var(--accent)',
                                fontFamily: 'var(--mono)',
                                fontSize: 11,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4,
                              }}
                            >
                              {copiedId === rec.id ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
                              {rec.id}
                            </button>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{rec.date_formatted || rec.timestamp}</span>
                            {rec.amount_formatted && (
                              <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--accent)' }}>{rec.amount_formatted}</span>
                            )}
                            {rec.duration_formatted && (
                              <span style={{ fontSize: 12, fontWeight: 700, color: '#00d2ff' }}>{rec.duration_formatted}</span>
                            )}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>
                            {rec.details}
                          </div>
                        </div>

                        {rec.deviation && (
                          <span style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', fontFamily: 'var(--mono)' }}>
                            {rec.deviation}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 2: Counterparties */}
              {activeModalTab === 'counterparties' && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: 8 }}>
                    Associated Counterparties & Transaction / Call Partners
                  </div>
                  {investigatingAnomaly.investigate_data.counterparties && investigatingAnomaly.investigate_data.counterparties.length > 0 ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
                      {investigatingAnomaly.investigate_data.counterparties.map((cp, idx) => (
                        <div
                          key={idx}
                          style={{
                            padding: '12px 14px',
                            borderRadius: 8,
                            background: 'rgba(0,0,0,0.3)',
                            border: '1px solid rgba(255,255,255,0.06)',
                          }}
                        >
                          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                            {cp.account_id || cp.contact}
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600, marginTop: 4 }}>
                            {cp.formatted_volume ? `Volume: ${cp.formatted_volume}` : `Duration: ${cp.formatted_duration}`}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                            {cp.transaction_count ? `${cp.transaction_count} transactions` : `${cp.call_count} calls`}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>
                      No direct counterparty accounts recorded for this pattern.
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: Network Connections */}
              {activeModalTab === 'network' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)' }}>
                      Graph Network Links for {investigatingAnomaly.investigate_data.network?.primary_node}
                    </div>
                    <button
                      className="btn btn-secondary"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      onClick={() => {
                        setInvestigatingAnomaly(null)
                        onNavigate?.('network')
                      }}
                    >
                      <Network size={12} /> Open Full Graph
                    </button>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {investigatingAnomaly.investigate_data.network?.connections.map((conn, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '10px 14px',
                          borderRadius: 6,
                          background: 'rgba(0,0,0,0.3)',
                          border: '1px solid rgba(255,255,255,0.06)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: '#818cf8', fontWeight: 600 }}>
                            {conn.relationship}
                          </span>
                          <ArrowRight size={12} color="var(--text-faint)" />
                          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                            {conn.target}
                          </span>
                        </div>
                        {conn.volume && (
                          <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>
                            {conn.volume}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 4: Location & Trajectory */}
              {activeModalTab === 'location' && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: 8 }}>
                    Geospatial & Spatiotemporal Trajectory
                  </div>
                  {investigatingAnomaly.investigate_data.location ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
                      <div style={{ padding: 12, borderRadius: 6, background: 'rgba(0,0,0,0.3)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Core Routine Anchor</div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)', marginTop: 4 }}>
                          {investigatingAnomaly.investigate_data.location.core_anchor_city}
                        </div>
                      </div>
                      <div style={{ padding: 12, borderRadius: 6, background: 'rgba(0,0,0,0.3)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Cities Visited (24h)</div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b', marginTop: 4 }}>
                          {investigatingAnomaly.investigate_data.location.cities_visited?.join(' → ')}
                        </div>
                      </div>
                      <div style={{ padding: 12, borderRadius: 6, background: 'rgba(0,0,0,0.3)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Distance Traversed</div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)', marginTop: 4 }}>
                          {investigatingAnomaly.investigate_data.location.total_distance_km} km
                        </div>
                      </div>
                      <div style={{ padding: 12, borderRadius: 6, background: 'rgba(0,0,0,0.3)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Peak Kinematic Velocity</div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#ef4444', marginTop: 4 }}>
                          {investigatingAnomaly.investigate_data.location.peak_velocity_kmh} km/h
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>
                      Geospatial coordinates not applicable to this financial/telecom finding.
                    </div>
                  )}
                </div>
              )}

              {/* TAB 5: Timeline Progression */}
              {activeModalTab === 'timeline' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)' }}>
                      Chronological Event Progression
                    </div>
                    <button
                      className="btn btn-secondary"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      onClick={() => {
                        setInvestigatingAnomaly(null)
                        onNavigate?.('cdr')
                      }}
                    >
                      <Clock size={12} /> View Full Timeline
                    </button>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingLeft: 12, borderLeft: '2px solid rgba(255,255,255,0.1)' }}>
                    {investigatingAnomaly.investigate_data.timeline?.map((evt, idx) => (
                      <div key={idx} style={{ position: 'relative', paddingLeft: 14 }}>
                        <div style={{
                          position: 'absolute',
                          left: -19,
                          top: 4,
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          background: 'var(--accent)',
                        }} />
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                          {evt.date || evt.timestamp}
                        </div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>
                          {evt.title}
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                          {evt.description}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 6: Entity Dossier Profile */}
              {activeModalTab === 'entity' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)' }}>
                      Suspect & Account Intelligence
                    </div>
                    <button
                      className="btn btn-secondary"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      onClick={() => {
                        setInvestigatingAnomaly(null)
                        onNavigate?.('dossiers')
                      }}
                    >
                      <Eye size={12} /> Open Suspect Dossier
                    </button>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
                    {Object.entries(investigatingAnomaly.investigate_data.entity_profile || {}).map(([k, v]) => (
                      <div key={k} style={{ padding: 12, borderRadius: 6, background: 'rgba(0,0,0,0.3)' }}>
                        <div style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-faint)' }}>{k.replace(/_/g, ' ')}</div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)', marginTop: 4 }}>
                          {String(v)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 7: Model & Statistics */}
              {activeModalTab === 'model' && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: 8 }}>
                    Mathematical Calibration & Algorithm Parameters
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
                    {Object.entries(investigatingAnomaly.investigate_data.model_details || {}).map(([k, v]) => (
                      <div key={k} style={{ padding: 12, borderRadius: 6, background: 'rgba(0,0,0,0.3)' }}>
                        <div style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-faint)' }}>{k.replace(/_/g, ' ')}</div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: '#818cf8', marginTop: 4, fontFamily: 'var(--mono)' }}>
                          {String(v)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer Actions */}
            <div style={{
              padding: '14px 24px',
              borderTop: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'rgba(15, 23, 42, 0.9)',
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>
                Case: <strong>{investigatingAnomaly.case_id}</strong> • Score: <strong>{investigatingAnomaly.anomaly_score_100}/100</strong>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => setInvestigatingAnomaly(null)}
                >
                  Close
                </button>
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setInvestigatingAnomaly(null)
                    onNavigate?.('audit')
                  }}
                >
                  Verify Evidence Chain →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Users(props: any) {
  return <UserCheck {...props} />
}
