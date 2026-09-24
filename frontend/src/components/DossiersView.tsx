// Suspect Dossiers & Network Leadership/Centrality Scoring View
import React, { useState, useEffect, useMemo } from 'react'
import {
  Users, Search, ChevronRight, Phone, Car, Building, AlertTriangle,
  Briefcase, Shield, ShieldAlert, Activity, CreditCard, Layers, MapPin,
  Clock, Lock, FileText, CheckCircle2, ExternalLink, Share2, Hash,
  ArrowUpRight, ArrowDownRight, Sparkles, Smartphone, Sliders, RefreshCw,
  Info, Award, TrendingUp, AlertCircle
} from 'lucide-react'

interface ScoreBreakdown {
  network_centrality: number
  betweenness_connectivity: number
  financial_influence: number
  communication_influence: number
  cross_case_connections: number
  evidence_strength: number
}

interface Kingpin {
  person_id: string
  full_name: string
  alias: string | null
  city: string | null
  occupation: string | null
  network_leadership_score: number
  leadership_score_100: number
  composite_score: number
  kingpin_score?: number
  role_classification: string
  rank: number
  confidence: number
  case_count: number
  explanation: string
  disclaimer: string
  betweenness_score?: number
  pagerank_score?: number
  financial_score?: number
  telecom_score?: number
  brokerage_score?: number
  cross_domain_score?: number
  degree_score?: number
  score_breakdown: ScoreBreakdown
  metrics: {
    betweenness_raw: number
    pagerank_raw: number
    degree_raw: number
    financial_volume_inr: number
    transaction_count: number
    call_count: number
    call_duration_seconds: number
    unique_contacts: number
    cases_count: number
    cases_list: string[]
    firs_count: number
    evidence_count: number
  }
}

interface Dossier {
  person_id: string
  full_name: string
  alias?: string | null
  age?: number | null
  gender?: string | null
  city?: string | null
  occupation?: string | null
  address?: string | null
  visited_cities: string[]
  phones: string[]
  phone_details: Array<{
    phone_id: string
    number: string
    sim_cards: string[]
  }>
  hardware_devices: Array<{
    device_id: string
    imei: string
    make: string
    model: string
    phone_id?: string
    is_primary?: boolean
  }>
  vehicles: Array<{
    vehicle_id: string
    registration_id: string
    make: string
    model: string
    color: string
    type?: string
    city?: string
  }>
  bank_accounts: Array<{
    account_id: string
    bank_name: string
    branch_city?: string
    account_type?: string
    inflow: number
    outflow: number
    tx_count: number
  }>
  linked_firs: Array<{
    fir_id: string
    fir_number: string
    case_id: string
    crime_type?: string
    role?: string
    confidence?: number
    status?: string
    incident_date?: string
    incident_city?: string
    summary?: string
  }>
  financial_activity: {
    total_sent_inr: number
    total_received_inr: number
    total_volume_inr: number
    transaction_count: number
    transactions: Array<{
      transaction_id: string
      case_id: string
      timestamp: string
      amount: number
      direction: 'INFLOW' | 'OUTFLOW'
      counterparty_account: string
      type?: string
      location?: string
      description?: string
    }>
  }
  cdr_activity: {
    total_calls: number
    calls_outgoing: number
    calls_incoming: number
    total_duration_seconds: number
    total_duration_formatted: string
    unique_contacts_count: number
    frequent_call_partners: Array<{
      phone_id: string
      call_count: number
      duration_seconds: number
      contact_name?: string
      contact_alias?: string
      contact_person_id?: string
    }>
    recent_calls: Array<{
      cdr_id: string
      case_id: string
      timestamp: string
      duration_seconds: number
      direction: 'INCOMING' | 'OUTGOING'
      counterparty_phone: string
      call_type?: string
      tower_location_id?: string
    }>
  }
  associates: Array<{
    relationship_id: string
    associate_id: string
    associate_name: string
    associate_alias?: string
    associate_city?: string
    associate_occupation?: string
    relationship_type: string
    confidence: number
    direction: 'INCOMING' | 'OUTGOING'
    timestamp?: string
  }>
  timeline: Array<{
    timestamp: string
    category: string
    title: string
    description: string
    case_id?: string
    evidence_id?: string
  }>
  anomalies: Array<{
    group_id?: string
    detector_name: string
    title: string
    anomaly_type: string
    severity: string
    anomaly_score_100: number
    what_happened: string
    why_unusual?: string
    evidence?: string[]
  }>
  evidence_references: Array<{
    evidence_id: string
    case_id: string
    source_table: string
    record_id: string
    evidence_type: string
    collected_date?: string
    custodian?: string
    content_sha256: string
  }>
  leadership_scoring: Kingpin
  disclaimer: string
}

interface CaseItem {
  case_id: string
  case_title: string
  crime_type: string
  primary_location?: string
  n_network_entities?: number
}

const SCORE_COLORS = ['#ef4444', '#f59e0b', '#06b6d4', '#10b981', '#8b5cf6']

export default function DossiersView() {
  const [cases, setCases] = useState<CaseItem[]>([])
  const [selectedCase, setSelectedCase] = useState<string>('ALL')
  const [kingpins, setKingpins] = useState<Kingpin[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Kingpin | null>(null)
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [dossierLoading, setDossierLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState<'leadership' | 'identity' | 'activity' | 'associates' | 'anomalies' | 'timeline' | 'evidence'>('leadership')
  const [roleFilter, setRoleFilter] = useState<'ALL' | 'ORCHESTRATOR' | 'BROKER' | 'CROSS_CASE'>('ALL')

  // 1. Fetch case directory
  useEffect(() => {
    const fetchCases = async () => {
      try {
        const res = await fetch('/api/cases?limit=100')
        if (res.ok) {
          const data = await res.json()
          setCases(data || [])
        }
      } catch (err) {
        console.error('Failed to load cases catalog', err)
      }
    }
    fetchCases()
  }, [])

  // 2. Fetch kingpins for selected case
  const loadKingpins = async (caseId: string) => {
    setLoading(true)
    try {
      const url = caseId && caseId !== 'ALL'
        ? `/api/analytics/kingpins?case_id=${caseId}&limit=500`
        : '/api/analytics/kingpins?limit=500'
      const r = await fetch(url)
      const d = await r.json()
      const candidates: Kingpin[] = d.candidates || []
      setKingpins(candidates)
      if (candidates.length > 0) {
        // Auto-select top-ranked candidate
        loadDossier(candidates[0], caseId)
      } else {
        setSelected(null)
        setDossier(null)
      }
    } catch {
      setKingpins([])
      setSelected(null)
      setDossier(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadKingpins(selectedCase)
  }, [selectedCase])

  // 3. Load full 360° suspect dossier
  const loadDossier = async (k: Kingpin, caseIdContext?: string) => {
    setSelected(k)
    setDossierLoading(true)
    try {
      const cParam = (caseIdContext && caseIdContext !== 'ALL') ? `?case_id=${caseIdContext}` : ''
      const r = await fetch(`/api/persons/${k.person_id}${cParam}`)
      const d = await r.json()
      setDossier(d)
    } catch {
      setDossier(null)
    } finally {
      setDossierLoading(false)
    }
  }

  // Filtered suspect roster
  const filteredCandidates = useMemo(() => {
    return kingpins.filter(k => {
      const q = searchQuery.toLowerCase().trim()
      const matchesSearch =
        !q ||
        k.full_name.toLowerCase().includes(q) ||
        (k.alias && k.alias.toLowerCase().includes(q)) ||
        k.person_id.toLowerCase().includes(q) ||
        (k.city && k.city.toLowerCase().includes(q))

      if (!matchesSearch) return false

      if (roleFilter === 'ORCHESTRATOR') {
        return (k.leadership_score_100 || k.composite_score * 100) >= 40
      }
      if (roleFilter === 'BROKER') {
        return (k.score_breakdown?.betweenness_connectivity || k.betweenness_score || 0) >= 0.25
      }
      if (roleFilter === 'CROSS_CASE') {
        return (k.case_count || k.metrics?.cases_count || 0) > 1
      }
      return true
    })
  }, [kingpins, searchQuery, roleFilter])

  // Scoring Pillar Component
  const PillarCard = ({
    title,
    weight,
    score,
    color,
    desc,
    valueStr
  }: {
    title: string
    weight: string
    score: number
    color: string
    desc: string
    valueStr?: string
  }) => {
    const pct = Math.min(100, Math.max(0, Math.round(score * 100)))
    return (
      <div style={{
        padding: '12px 14px',
        background: 'rgba(255,255,255,0.02)',
        borderRadius: 8,
        border: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 6
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>{title}</span>
            <span style={{ fontSize: 10, color: 'var(--text-faint)', marginLeft: 6 }}>({weight})</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {valueStr && <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{valueStr}</span>}
            <span style={{ fontSize: 13, fontWeight: 800, color, fontFamily: 'var(--mono)' }}>{pct}%</span>
          </div>
        </div>
        <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            borderRadius: 3,
            background: color,
            width: `${pct}%`,
            transition: 'width 0.4s ease'
          }} />
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-faint)', lineHeight: 1.4 }}>{desc}</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── Top Header & Case Scoping Banner ─────────────────────────────────── */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: 'rgba(0,210,255,0.1)', border: '1px solid rgba(0,210,255,0.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Users size={18} color="var(--accent)" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
                  Suspect Dossiers & Network Leadership Scoring
                </h2>
                <span className="badge badge-accent">{filteredCandidates.length} Entities Evaluated</span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)' }}>
                360° individual suspect intelligence & 6-pillar topological centrality rankings across network cases.
              </p>
            </div>
          </div>

          {/* Case Selector Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)' }}>Scope Case:</span>
              <select
                id="case-select-dropdown"
                value={selectedCase}
                onChange={e => setSelectedCase(e.target.value)}
                style={{
                  background: 'var(--surface-dark, #0f172a)',
                  color: 'var(--text-bright, #f8fafc)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '6px 12px',
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  maxWidth: 280,
                }}
              >
                <option value="ALL">🌐 All Cases (Global Syndicate Graph)</option>
                {cases.map(c => (
                  <option key={c.case_id} value={c.case_id}>
                    {c.case_id} — {c.case_title} ({c.crime_type})
                  </option>
                ))}
              </select>
            </div>

            <button
              className="btn btn-secondary"
              onClick={() => loadKingpins(selectedCase)}
              title="Refresh Scoring"
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              Recompute
            </button>
          </div>
        </div>

        {/* Legal & Analytical Disclaimer Alert */}
        <div style={{
          padding: '8px 14px',
          borderRadius: 6,
          background: 'rgba(245, 158, 11, 0.08)',
          border: '1px solid rgba(245, 158, 11, 0.25)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <AlertTriangle size={15} color="#f59e0b" style={{ flexShrink: 0 }} />
          <div style={{ fontSize: 11, color: '#fef3c7', lineHeight: 1.4 }}>
            <strong>LEGAL & METHODOLOGICAL NOTICE:</strong> Network Leadership/Centrality Scores evaluate mathematical centrality, communication density, financial flow, and structural brokerage within the evidence graph. <strong>This is NOT a measure of legal guilt probability.</strong> All findings require corroborating forensic testimony and investigator review.
          </div>
        </div>
      </div>

      {/* ── Main Layout: 2-Column Split ──────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: selected ? '380px 1fr' : '1fr', gap: 16, alignItems: 'start' }}>
        
        {/* ── Left Column: Ranked Suspect Cards Roster ───────────────────────── */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', maxHeight: 'calc(100vh - 170px)', overflow: 'hidden' }}>
          {/* Controls Bar */}
          <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div className="topbar-search" style={{ margin: 0, width: '100%' }}>
              <Search className="search-icon" size={14} />
              <input
                id="suspect-search-input"
                type="text"
                placeholder="Search suspect name, alias, ID, or city…"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{ fontSize: 12 }}
              />
            </div>

            {/* Quick Filter Chips */}
            <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 2 }}>
              <button
                className={`btn btn-xs ${roleFilter === 'ALL' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ fontSize: 11, padding: '2px 8px' }}
                onClick={() => setRoleFilter('ALL')}
              >
                All ({kingpins.length})
              </button>
              <button
                className={`btn btn-xs ${roleFilter === 'ORCHESTRATOR' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ fontSize: 11, padding: '2px 8px' }}
                onClick={() => setRoleFilter('ORCHESTRATOR')}
              >
                Orchestrators (≥40)
              </button>
              <button
                className={`btn btn-xs ${roleFilter === 'BROKER' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ fontSize: 11, padding: '2px 8px' }}
                onClick={() => setRoleFilter('BROKER')}
              >
                Brokers
              </button>
              <button
                className={`btn btn-xs ${roleFilter === 'CROSS_CASE' ? 'btn-primary' : 'btn-ghost'}`}
                style={{ fontSize: 11, padding: '2px 8px' }}
                onClick={() => setRoleFilter('CROSS_CASE')}
              >
                Multi-Case
              </button>
            </div>
          </div>

          {/* Suspect Roster List */}
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {loading ? (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)', fontSize: 13 }}>
                <Activity size={20} className="animate-spin" style={{ margin: '0 auto 10px', color: 'var(--accent)' }} />
                Computing Network Leadership & Centrality ranks…
              </div>
            ) : filteredCandidates.length === 0 ? (
              <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-faint)', fontSize: 13 }}>
                No suspect entities match current filter.
              </div>
            ) : (
              filteredCandidates.map((k, i) => {
                const isSelected = selected?.person_id === k.person_id
                const score = k.leadership_score_100 ?? Math.round(k.composite_score * 100)
                const rankColor = i < 3 ? SCORE_COLORS[i] : i < 8 ? '#f59e0b' : 'var(--text-faint)'

                return (
                  <div
                    key={k.person_id}
                    id={`suspect-card-${k.person_id}`}
                    onClick={() => loadDossier(k, selectedCase)}
                    style={{
                      padding: '12px 14px',
                      borderBottom: '1px solid var(--border)',
                      cursor: 'pointer',
                      background: isSelected ? 'rgba(0,210,255,0.08)' : 'transparent',
                      borderLeft: isSelected ? '3px solid var(--accent)' : '3px solid transparent',
                      transition: 'all 0.15s ease',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}
                    className="table-row-hover"
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      {/* Rank Badge */}
                      <div style={{
                        width: 28, height: 28, borderRadius: '50%',
                        background: i < 3 ? `${rankColor}22` : 'rgba(255,255,255,0.05)',
                        border: `1px solid ${i < 3 ? rankColor : 'rgba(255,255,255,0.1)'}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0
                      }}>
                        <span style={{ fontSize: 11, fontWeight: 800, color: rankColor }}>
                          #{k.rank || i + 1}
                        </span>
                      </div>

                      {/* Name & Identifiers */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {k.full_name}
                          </span>
                          {k.alias && (
                            <span style={{ fontSize: 11, color: 'var(--amber)', whiteSpace: 'nowrap' }}>
                              aka {k.alias}
                            </span>
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 2 }}>
                          <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-faint)' }}>{k.person_id}</span>
                          {k.city && <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>• {k.city}</span>}
                          {k.occupation && <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>• {k.occupation}</span>}
                        </div>
                      </div>

                      {/* Leadership Score */}
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <div style={{
                          fontSize: 18,
                          fontWeight: 800,
                          fontFamily: 'var(--mono)',
                          color: score >= 50 ? 'var(--red)' : score >= 35 ? 'var(--amber)' : score >= 20 ? 'var(--accent)' : 'var(--text-muted)'
                        }}>
                          {score}
                        </div>
                        <div style={{ fontSize: 9, color: 'var(--text-faint)', textTransform: 'uppercase' }}>
                          Leadership
                        </div>
                      </div>
                    </div>

                    {/* Quick Metric Pills */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, paddingTop: 4, borderTop: '1px dashed rgba(255,255,255,0.06)' }}>
                      <span className="badge badge-default" style={{ fontSize: 10, padding: '1px 6px' }}>
                        {k.role_classification || 'Operational Associate'}
                      </span>
                      <div style={{ display: 'flex', gap: 8, fontSize: 10, color: 'var(--text-faint)' }}>
                        <span>Cases: <strong style={{ color: 'var(--text-dim)' }}>{k.metrics?.cases_count || k.case_count || 1}</strong></span>
                        <span>Calls: <strong style={{ color: 'var(--text-dim)' }}>{k.metrics?.call_count ?? 0}</strong></span>
                        {k.metrics?.financial_volume_inr ? (
                          <span>₹<strong style={{ color: 'var(--text-dim)' }}>{(k.metrics.financial_volume_inr / 1000).toFixed(0)}k</strong></span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* ── Right Column: 360° Comprehensive Suspect Dossier ────────────────── */}
        {selected ? (
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            
            {/* Dossier Header Card */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid var(--border)',
              background: 'linear-gradient(180deg, rgba(0,210,255,0.04) 0%, rgba(0,0,0,0) 100%)'
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
                <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
                  <div style={{
                    width: 52, height: 52, borderRadius: 12,
                    background: 'rgba(0,210,255,0.12)', border: '1px solid rgba(0,210,255,0.3)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 22, fontWeight: 800, color: 'var(--accent)'
                  }}>
                    {selected.full_name.charAt(0)}
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <h3 style={{ fontSize: 18, fontWeight: 800, margin: 0, color: 'var(--text-bright)' }}>
                        {selected.full_name}
                      </h3>
                      {selected.alias && (
                        <span className="badge badge-warning" style={{ fontSize: 11 }}>
                          Alias: {selected.alias}
                        </span>
                      )}
                      <span className="badge badge-default" style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
                        {selected.person_id}
                      </span>
                    </div>

                    <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 4, fontSize: 12, color: 'var(--text-muted)' }}>
                      <span>City: <strong style={{ color: 'var(--text)' }}>{dossier?.city || selected.city || 'Undisclosed'}</strong></span>
                      <span>Occupation: <strong style={{ color: 'var(--text)' }}>{dossier?.occupation || selected.occupation || 'Unknown'}</strong></span>
                      {dossier?.age && <span>Age: <strong style={{ color: 'var(--text)' }}>{dossier.age}</strong></span>}
                      {dossier?.gender && <span>Gender: <strong style={{ color: 'var(--text)' }}>{dossier.gender}</strong></span>}
                    </div>
                  </div>
                </div>

                {/* Big Metric Badge */}
                <div style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid var(--border)',
                  textAlign: 'right'
                }}>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Leadership/Centrality Score
                  </div>
                  <div style={{
                    fontSize: 24,
                    fontWeight: 900,
                    fontFamily: 'var(--mono)',
                    color: (selected.leadership_score_100 ?? selected.composite_score * 100) >= 40 ? 'var(--red)' : 'var(--amber)'
                  }}>
                    {selected.leadership_score_100 ?? Math.round(selected.composite_score * 100)}/100
                  </div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)' }}>
                    {selected.role_classification}
                  </div>
                </div>
              </div>

              {/* Navigation Sub-Tabs */}
              <div style={{ display: 'flex', gap: 6, marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 12, overflowX: 'auto' }}>
                {[
                  { id: 'leadership', label: '🌟 Leadership & Centrality', count: null },
                  { id: 'identity',   label: '👤 Identity & Assets', count: (dossier?.phones.length || 0) + (dossier?.vehicles.length || 0) },
                  { id: 'activity',   label: '📊 CDR & Financial Flow', count: (dossier?.financial_activity?.transaction_count || 0) + (dossier?.cdr_activity?.total_calls || 0) },
                  { id: 'associates', label: '🕸️ Associates', count: dossier?.associates.length },
                  { id: 'anomalies',  label: '🚨 Anomalies', count: dossier?.anomalies.length },
                  { id: 'timeline',   label: '🕒 Forensic Timeline', count: dossier?.timeline.length },
                  { id: 'evidence',   label: '🔒 Evidence References', count: dossier?.evidence_references.length },
                ].map(tab => (
                  <button
                    key={tab.id}
                    className={`btn btn-xs ${activeTab === tab.id ? 'btn-primary' : 'btn-ghost'}`}
                    style={{ fontSize: 11, padding: '4px 10px', whiteSpace: 'nowrap' }}
                    onClick={() => setActiveTab(tab.id as any)}
                  >
                    {tab.label}
                    {tab.count !== null && tab.count !== undefined && (
                      <span style={{
                        marginLeft: 6, padding: '1px 5px', borderRadius: 10,
                        background: activeTab === tab.id ? 'rgba(0,0,0,0.3)' : 'rgba(255,255,255,0.1)',
                        fontSize: 10
                      }}>
                        {tab.count}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Dossier Body Content */}
            <div style={{ padding: 20, overflowY: 'auto', maxHeight: 'calc(100vh - 310px)' }}>
              {dossierLoading ? (
                <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-faint)' }}>
                  <Activity size={24} className="animate-spin" style={{ margin: '0 auto 12px', color: 'var(--accent)' }} />
                  Assembling 360° forensic profile and evidentiary ledger…
                </div>
              ) : (
                <>
                  {/* ── TAB 1: LEADERSHIP & CENTRALITY (6 PILLARS) ────────────────── */}
                  {activeTab === 'leadership' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                      
                      {/* Explanation Card */}
                      <div style={{
                        padding: '14px 16px',
                        borderRadius: 8,
                        background: 'rgba(0,210,255,0.03)',
                        border: '1px solid rgba(0,210,255,0.15)',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                          <Sparkles size={16} color="var(--accent)" />
                          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                            Topological Leadership & Role Analysis
                          </span>
                        </div>
                        <p style={{ margin: 0, fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                          {selected.explanation}
                        </p>
                      </div>

                      {/* 6 Pillars Grid */}
                      <div>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
                          Mathematical Scoring Pillars Breakdown
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
                          <PillarCard
                            title="1. Network Centrality"
                            weight="20%"
                            score={selected.score_breakdown?.network_centrality || selected.degree_score || 0}
                            color="#ef4444"
                            valueStr={`PageRank: ${(selected.metrics?.pagerank_raw || selected.pagerank_score || 0).toFixed(4)}`}
                            desc="Structural prominence and authority in graph topology based on PageRank and direct degree centrality."
                          />
                          <PillarCard
                            title="2. Betweenness / Connectivity"
                            weight="20%"
                            score={selected.score_breakdown?.betweenness_connectivity || selected.betweenness_score || 0}
                            color="#f59e0b"
                            valueStr={`Betweenness: ${(selected.metrics?.betweenness_raw || selected.betweenness_score || 0).toFixed(4)}`}
                            desc="Information and operational choke-point score; frequency this entity sits on shortest paths connecting disparate sub-cliques."
                          />
                          <PillarCard
                            title="3. Financial Influence"
                            weight="20%"
                            score={selected.score_breakdown?.financial_influence || selected.financial_score || 0}
                            color="#06b6d4"
                            valueStr={`₹${(selected.metrics?.financial_volume_inr || 0).toLocaleString()}`}
                            desc="Direct volume of transaction funds routed, sender/receiver control, and high-frequency mule funnel activity."
                          />
                          <PillarCard
                            title="4. Communication Influence"
                            weight="15%"
                            score={selected.score_breakdown?.communication_influence || selected.telecom_score || 0}
                            color="#10b981"
                            valueStr={`${selected.metrics?.call_count || 0} Calls / ${selected.metrics?.unique_contacts || 0} Contacts`}
                            desc="Call frequency, burst intensity, unique contact phone reach, and duration across CDR records."
                          />
                          <PillarCard
                            title="5. Cross-Case Connections"
                            weight="15%"
                            score={selected.score_breakdown?.cross_case_connections || selected.cross_domain_score || 0}
                            color="#8b5cf6"
                            valueStr={`${selected.metrics?.cases_count || selected.case_count || 1} Cases`}
                            desc="Syndicate footprint spanning multiple distinct FIR investigations and cross-jurisdiction operational overlap."
                          />
                          <PillarCard
                            title="6. Evidence Strength"
                            weight="10%"
                            score={selected.score_breakdown?.evidence_strength || 0.8}
                            color="#ec4899"
                            valueStr={`${selected.metrics?.evidence_count || 12} Evidence Links`}
                            desc="Empirical density of verified physical, telecom, and financial ledger items referencing this suspect."
                          />
                        </div>
                      </div>

                      {/* Raw Metrics Bar */}
                      <div style={{
                        padding: '12px 16px',
                        background: 'rgba(255,255,255,0.02)',
                        borderRadius: 8,
                        border: '1px solid var(--border)',
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                        gap: 12,
                        textAlign: 'center'
                      }}>
                        <div>
                          <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Total Transactions</div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>
                            {selected.metrics?.transaction_count || 0}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Total Talk-Time</div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>
                            {Math.round((selected.metrics?.call_duration_seconds || 0) / 60)} mins
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>FIR Charges</div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>
                            {selected.metrics?.firs_count || selected.case_count || 1}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Syndicate Cases</div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent)', marginTop: 2 }}>
                            {selected.metrics?.cases_count || 1}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* ── TAB 2: IDENTITY & LINKED ASSETS ───────────────────────── */}
                  {activeTab === 'identity' && dossier && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                      {/* Demographics */}
                      <div style={{ padding: 14, background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10 }}>
                          Demographics & Known Aliases
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
                          <div>
                            <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Full Name</div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{dossier.full_name}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Aliases / Street Names</div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: dossier.alias ? 'var(--amber)' : 'var(--text-muted)' }}>
                              {dossier.alias || 'None recorded'}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>City / Region</div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{dossier.city || 'Unspecified'}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Occupation / Cover</div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{dossier.occupation || 'Unrecorded'}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Residential / Address</div>
                            <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>{dossier.address || 'Address unverified'}</div>
                          </div>
                          <div>
                            <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Visited / Sightings Cities</div>
                            <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                              {dossier.visited_cities?.join(', ') || dossier.city || 'N/A'}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Linked Phones & Devices */}
                      <div style={{ padding: 14, background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Smartphone size={13} color="var(--green)" />
                          Linked Telecom Subscriptions & Hardware Devices ({dossier.phones.length})
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
                          {dossier.phone_details?.map(p => (
                            <div key={p.phone_id} style={{ padding: 10, background: 'rgba(16,185,129,0.05)', borderRadius: 6, border: '1px solid rgba(16,185,129,0.2)' }}>
                              <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--green)' }}>
                                {p.number}
                              </div>
                              <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 2 }}>
                                Phone ID: {p.phone_id} {p.sim_cards?.length ? `• ${p.sim_cards.join(', ')}` : ''}
                              </div>
                            </div>
                          ))}
                        </div>

                        {dossier.hardware_devices?.length > 0 && (
                          <div style={{ marginTop: 12, borderTop: '1px dashed var(--border)', paddingTop: 10 }}>
                            <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 6 }}>
                              Hardware Handsets (IMEIs):
                            </div>
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                              {dossier.hardware_devices.map(h => (
                                <span key={h.device_id} className="badge badge-default" style={{ fontSize: 11, fontFamily: 'var(--mono)' }}>
                                  IMEI: {h.imei} ({h.make} {h.model})
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Bank Accounts */}
                      <div style={{ padding: 14, background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                          <CreditCard size={13} color="var(--accent)" />
                          Linked Financial & Bank Accounts ({dossier.bank_accounts.length})
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
                          {dossier.bank_accounts.map(b => (
                            <div key={b.account_id} style={{ padding: 10, background: 'rgba(0,210,255,0.04)', borderRadius: 6, border: '1px solid rgba(0,210,255,0.2)' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
                                  {b.account_id}
                                </span>
                                <span className="badge badge-default" style={{ fontSize: 9 }}>{b.account_type || 'Savings'}</span>
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--text-bright)', marginTop: 4 }}>{b.bank_name}</div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-faint)', marginTop: 4 }}>
                                <span>In: ₹{b.inflow.toLocaleString()}</span>
                                <span>Out: ₹{b.outflow.toLocaleString()}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Vehicles */}
                      <div style={{ padding: 14, background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Car size={13} color="var(--amber)" />
                          Registered Vehicles ({dossier.vehicles.length})
                        </div>
                        {dossier.vehicles.length === 0 ? (
                          <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>No registered vehicles under suspect's name.</div>
                        ) : (
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
                            {dossier.vehicles.map(v => (
                              <div key={v.vehicle_id} style={{ padding: 10, background: 'rgba(245,158,11,0.04)', borderRadius: 6, border: '1px solid rgba(245,158,11,0.2)' }}>
                                <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--amber)' }}>
                                  {v.registration_id}
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--text)', marginTop: 2 }}>
                                  {v.make} {v.model} ({v.color})
                                </div>
                                <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 2 }}>
                                  Type: {v.type || 'Passenger'} • {v.city || 'Local'}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Linked FIRs */}
                      <div style={{ padding: 14, background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border)' }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                          <FileText size={13} color="var(--red)" />
                          FIR Involvements & Legal Allegations ({dossier.linked_firs.length})
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          {dossier.linked_firs.map(f => (
                            <div key={f.fir_id} style={{ padding: 10, background: 'rgba(239,68,68,0.04)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--red)' }}>{f.fir_number}</span>
                                  <span className="badge badge-accent" style={{ fontSize: 10 }}>{f.case_id}</span>
                                  <span className="badge badge-default" style={{ fontSize: 10 }}>Role: {f.role}</span>
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 3 }}>
                                  {f.summary || `${f.crime_type} registered in ${f.incident_city}`}
                                </div>
                              </div>
                              <span className="badge badge-warning" style={{ fontSize: 10 }}>{f.status}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* ── TAB 3: CDR & FINANCIAL ACTIVITY ───────────────────────── */}
                  {activeTab === 'activity' && dossier && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                      {/* Financial Flow Section */}
                      <div style={{ padding: 14, background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <CreditCard size={14} color="var(--accent)" />
                            Financial Flow Analysis
                          </div>
                          <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
                            <span>In: <strong style={{ color: 'var(--green)' }}>₹{dossier.financial_activity.total_received_inr.toLocaleString()}</strong></span>
                            <span>Out: <strong style={{ color: 'var(--red)' }}>₹{dossier.financial_activity.total_sent_inr.toLocaleString()}</strong></span>
                            <span>Total Volume: <strong style={{ color: 'var(--accent)' }}>₹{dossier.financial_activity.total_volume_inr.toLocaleString()}</strong></span>
                          </div>
                        </div>

                        {dossier.financial_activity.transactions?.length === 0 ? (
                          <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>No recorded transactions for suspect's accounts.</div>
                        ) : (
                          <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
                              <thead>
                                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-faint)' }}>
                                  <th style={{ padding: '6px 8px' }}>TX ID</th>
                                  <th style={{ padding: '6px 8px' }}>Timestamp</th>
                                  <th style={{ padding: '6px 8px' }}>Flow</th>
                                  <th style={{ padding: '6px 8px' }}>Amount</th>
                                  <th style={{ padding: '6px 8px' }}>Counterparty Account</th>
                                  <th style={{ padding: '6px 8px' }}>Type</th>
                                </tr>
                              </thead>
                              <tbody>
                                {dossier.financial_activity.transactions.map(t => (
                                  <tr key={t.transaction_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                    <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{t.transaction_id}</td>
                                    <td style={{ padding: '6px 8px', color: 'var(--text-dim)' }}>{t.timestamp}</td>
                                    <td style={{ padding: '6px 8px' }}>
                                      <span style={{
                                        fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
                                        background: t.direction === 'INFLOW' ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                                        color: t.direction === 'INFLOW' ? 'var(--green)' : 'var(--red)',
                                      }}>
                                        {t.direction}
                                      </span>
                                    </td>
                                    <td style={{ padding: '6px 8px', fontWeight: 600, color: 'var(--text-bright)' }}>₹{t.amount.toLocaleString()}</td>
                                    <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{t.counterparty_account}</td>
                                    <td style={{ padding: '6px 8px', color: 'var(--text-faint)' }}>{t.type || 'TRANSFER'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>

                      {/* Telecom CDR Activity */}
                      <div style={{ padding: 14, background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Phone size={14} color="var(--green)" />
                            Telecom & CDR Activity ({dossier.cdr_activity.total_calls} Calls)
                          </div>
                          <div style={{ display: 'flex', gap: 12, fontSize: 12, color: 'var(--text-dim)' }}>
                            <span>Outgoing: <strong>{dossier.cdr_activity.calls_outgoing}</strong></span>
                            <span>Incoming: <strong>{dossier.cdr_activity.calls_incoming}</strong></span>
                            <span>Duration: <strong>{dossier.cdr_activity.total_duration_formatted}</strong></span>
                            <span>Contacts: <strong style={{ color: 'var(--accent)' }}>{dossier.cdr_activity.unique_contacts_count}</strong></span>
                          </div>
                        </div>

                        {/* Top Interacted Contacts */}
                        {dossier.cdr_activity.frequent_call_partners?.length > 0 && (
                          <div style={{ marginBottom: 14 }}>
                            <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 6 }}>
                              Top Frequent Call Partners:
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8 }}>
                              {dossier.cdr_activity.frequent_call_partners.map(p => (
                                <div key={p.phone_id} style={{ padding: '8px 10px', background: 'rgba(255,255,255,0.02)', borderRadius: 6, border: '1px solid var(--border)' }}>
                                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-bright)' }}>
                                    {p.contact_name} {p.contact_alias ? `(${p.contact_alias})` : ''}
                                  </div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-faint)', marginTop: 3 }}>
                                    <span style={{ fontFamily: 'var(--mono)' }}>{p.phone_id}</span>
                                    <span style={{ color: 'var(--green)' }}>{p.call_count} calls ({Math.round(p.duration_seconds / 60)}m)</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Call Logs Table */}
                        {dossier.cdr_activity.recent_calls?.length > 0 && (
                          <div style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
                              <thead>
                                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-faint)' }}>
                                  <th style={{ padding: '6px 8px' }}>CDR ID</th>
                                  <th style={{ padding: '6px 8px' }}>Timestamp</th>
                                  <th style={{ padding: '6px 8px' }}>Direction</th>
                                  <th style={{ padding: '6px 8px' }}>Counterparty</th>
                                  <th style={{ padding: '6px 8px' }}>Duration</th>
                                  <th style={{ padding: '6px 8px' }}>Tower Loc</th>
                                </tr>
                              </thead>
                              <tbody>
                                {dossier.cdr_activity.recent_calls.map(c => (
                                  <tr key={c.cdr_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                    <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)', color: 'var(--green)' }}>{c.cdr_id}</td>
                                    <td style={{ padding: '6px 8px', color: 'var(--text-dim)' }}>{c.timestamp}</td>
                                    <td style={{ padding: '6px 8px' }}>
                                      <span style={{
                                        fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
                                        background: c.direction === 'OUTGOING' ? 'rgba(59,130,246,0.1)' : 'rgba(16,185,129,0.1)',
                                        color: c.direction === 'OUTGOING' ? 'var(--info)' : 'var(--green)',
                                      }}>
                                        {c.direction}
                                      </span>
                                    </td>
                                    <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{c.counterparty_phone}</td>
                                    <td style={{ padding: '6px 8px', color: 'var(--text)' }}>{c.duration_seconds}s</td>
                                    <td style={{ padding: '6px 8px', color: 'var(--text-faint)' }}>{c.tower_location_id || 'N/A'}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ── TAB 4: ASSOCIATES & NETWORK CONNECTIONS ──────────────── */}
                  {activeTab === 'associates' && dossier && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>
                        Direct Graph Associates & Relationships ({dossier.associates.length})
                      </div>
                      {dossier.associates.length === 0 ? (
                        <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>No direct graph edges observed.</div>
                      ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
                          {dossier.associates.map(a => (
                            <div key={a.relationship_id} style={{
                              padding: 12,
                              background: 'rgba(255,255,255,0.02)',
                              borderRadius: 8,
                              border: '1px solid var(--border)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 6
                            }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                                    {a.associate_name}
                                  </div>
                                  {a.associate_alias && (
                                    <div style={{ fontSize: 11, color: 'var(--amber)' }}>aka {a.associate_alias}</div>
                                  )}
                                </div>
                                <span className="badge badge-accent" style={{ fontSize: 10 }}>
                                  {a.relationship_type}
                                </span>
                              </div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-faint)', marginTop: 4 }}>
                                <span>ID: <strong style={{ color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>{a.associate_id}</strong></span>
                                <span>City: {a.associate_city || 'N/A'}</span>
                                <span>Confidence: {(a.confidence * 100).toFixed(0)}%</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── TAB 5: FORENSIC ANOMALIES ─────────────────────────────── */}
                  {activeTab === 'anomalies' && dossier && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>
                        Flagged Forensic Anomalies & Typologies ({dossier.anomalies.length})
                      </div>
                      {dossier.anomalies.length === 0 ? (
                        <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-faint)', fontSize: 12 }}>
                          No active detector anomalies flagged for this entity.
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                          {dossier.anomalies.map((an, idx) => (
                            <div key={idx} style={{
                              padding: 12,
                              background: an.severity === 'CRITICAL' ? 'rgba(239,68,68,0.06)' : 'rgba(245,158,11,0.06)',
                              borderRadius: 8,
                              border: `1px solid ${an.severity === 'CRITICAL' ? 'rgba(239,68,68,0.25)' : 'rgba(245,158,11,0.25)'}`,
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 6
                            }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                  <AlertCircle size={15} color={an.severity === 'CRITICAL' ? 'var(--red)' : 'var(--amber)'} />
                                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>{an.title}</span>
                                </div>
                                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                  <span className={`badge ${an.severity === 'CRITICAL' ? 'badge-danger' : 'badge-warning'}`} style={{ fontSize: 10 }}>
                                    {an.severity}
                                  </span>
                                  <span style={{ fontSize: 11, fontWeight: 800, fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
                                    Score: {an.anomaly_score_100}
                                  </span>
                                </div>
                              </div>
                              <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                                {an.what_happened}
                              </div>
                              {an.why_unusual && (
                                <div style={{ fontSize: 11, color: 'var(--text-faint)', fontStyle: 'italic' }}>
                                  Deviation: {an.why_unusual}
                                </div>
                              )}
                              {an.evidence?.length ? (
                                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                                  {an.evidence.map(ev => (
                                    <span key={ev} style={{ fontSize: 9, fontFamily: 'var(--mono)', padding: '1px 5px', borderRadius: 3, background: 'rgba(255,255,255,0.05)', color: 'var(--text-dim)' }}>
                                      {ev}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── TAB 6: FORENSIC TIMELINE ──────────────────────────────── */}
                  {activeTab === 'timeline' && dossier && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>
                        Forensic Chronological Timeline ({dossier.timeline.length} Events)
                      </div>
                      {dossier.timeline.length === 0 ? (
                        <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>No chronological events recorded.</div>
                      ) : (
                        <div style={{ position: 'relative', paddingLeft: 20, borderLeft: '2px solid var(--border)', marginLeft: 8 }}>
                          {dossier.timeline.map((ev, i) => (
                            <div key={i} style={{ marginBottom: 16, position: 'relative' }}>
                              {/* Dot */}
                              <div style={{
                                position: 'absolute', left: -25, top: 2, width: 10, height: 10, borderRadius: '50%',
                                background: ev.category === 'FINANCIAL' ? 'var(--accent)' : ev.category === 'CDR' ? 'var(--green)' : ev.category === 'FIR_INCIDENT' ? 'var(--red)' : 'var(--amber)'
                              }} />
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-faint)' }}>{ev.timestamp}</span>
                                <span className="badge badge-default" style={{ fontSize: 9 }}>{ev.category}</span>
                                {ev.case_id && <span className="badge badge-accent" style={{ fontSize: 9 }}>{ev.case_id}</span>}
                              </div>
                              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-bright)', marginTop: 2 }}>{ev.title}</div>
                              <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>{ev.description}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── TAB 7: EVIDENCE REFERENCES & HASH CHAIN ──────────────── */}
                  {activeTab === 'evidence' && dossier && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Lock size={14} color="var(--accent)" />
                        Verifiable Evidence Ledger & Cryptographic SHA-256 Hashes ({dossier.evidence_references.length})
                      </div>
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-faint)' }}>
                              <th style={{ padding: '6px 8px' }}>Evidence ID</th>
                              <th style={{ padding: '6px 8px' }}>Source Table</th>
                              <th style={{ padding: '6px 8px' }}>Record ID</th>
                              <th style={{ padding: '6px 8px' }}>Type</th>
                              <th style={{ padding: '6px 8px' }}>Custodian</th>
                              <th style={{ padding: '6px 8px' }}>SHA-256 Checksum</th>
                            </tr>
                          </thead>
                          <tbody>
                            {dossier.evidence_references.map(e => (
                              <tr key={e.evidence_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{e.evidence_id}</td>
                                <td style={{ padding: '6px 8px', color: 'var(--text-dim)' }}>{e.source_table}</td>
                                <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)', color: 'var(--text)' }}>{e.record_id}</td>
                                <td style={{ padding: '6px 8px', color: 'var(--text-faint)' }}>{e.evidence_type}</td>
                                <td style={{ padding: '6px 8px', color: 'var(--text-dim)' }}>{e.custodian || 'State Forensic Lab'}</td>
                                <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--green)' }}>
                                  {e.content_sha256.substring(0, 16)}…
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="glass-panel" style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)' }}>
            Select a suspect from the roster to inspect full 360° investigative dossier and leadership scoring.
          </div>
        )}
      </div>
    </div>
  )
}
