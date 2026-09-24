// CDR Intelligence View — Deep Forensic Telecom Analysis & Communication Timeline
import React, { useState, useEffect, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer
} from 'recharts'
import {
  Radio, Phone, Zap, AlertTriangle, Clock, MapPin, Users,
  Smartphone, ArrowRight, ArrowLeftRight, MessageSquare,
  ShieldAlert, Filter, Search, ChevronDown, ChevronUp, Eye
} from 'lucide-react'

type TabType = 'timeline' | 'frequent' | 'connectors' | 'temporal' | 'locations' | 'devices'

interface Party {
  phone_id: string
  number: string
  person_id?: string | null
  person_name: string
  alias?: string | null
  label: string
}

interface LocationInfo {
  location_id?: string | null
  name: string
  area?: string
  city?: string
  lat?: number
  lon?: number
}

interface TimelineEvent {
  event_type: 'CALL' | 'SMS' | 'MOVEMENT' | 'INCIDENT'
  timestamp: string
  party_a?: Party
  party_b?: Party
  call_type?: string
  duration_seconds?: number
  duration_formatted?: string
  location?: LocationInfo
  narrative: string
  cdr_id?: string
  event_id?: string
  fir_number?: string
  crime_type?: string
  relative_time?: string
  is_critical_anchor?: boolean
}

interface FrequentPair {
  party_a: Party
  party_b: Party
  total_calls: number
  total_duration_seconds: number
  total_duration_formatted: string
  average_duration_seconds: number
  a_to_b_calls: number
  b_to_a_calls: number
  voice_count: number
  sms_count: number
  first_contact?: string
  last_contact?: string
  severity: string
  explanation: string
}

interface HiddenConnector {
  connector: Party
  connected_parties_count: number
  connected_parties: Party[]
  disconnected_pairs_count: number
  disconnection_rate: number
  sample_bridged_pairs: { party_1: string; party_2: string }[]
  severity: string
  confidence: number
  explanation: string
}

interface TemporalSurge {
  detector_name: string
  incident_date: string
  baseline_daily_average: number
  pre_incident_daily_average: number
  surge_multiplier: number
  total_surge_calls: number
  severity: string
  confidence: number
  explanation: string
  daily_timeline: { date: string; calls: number }[]
}

interface LocationCorrelation {
  tower_id: string
  tower_name: string
  area: string
  city: string
  timestamp_window: string
  distinct_entities_count: number
  entities: Party[]
  event_count: number
  severity: string
  confidence: number
  explanation: string
}

interface CommonDevice {
  device_id: string
  imei: string
  make: string
  model: string
  sim_count: number
  sim_ids: string[]
  associated_persons: string[]
  phone_ids: string[]
  severity: string
  explanation: string
}

const SEV_COLOR: Record<string, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f59e0b',
  MEDIUM: '#38bdf8',
  LOW: '#64748b'
}

export default function CDRView() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [cases, setCases] = useState<string[]>([])
  const [selectedCase, setSelectedCase] = useState<string>('CASE001')
  const [tab, setTab] = useState<TabType>('timeline')
  const [expandedItem, setExpandedItem] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [timelineFilter, setTimelineFilter] = useState<string>('ALL')

  // Load available cases
  useEffect(() => {
    fetch('/api/cases?limit=100')
      .then(r => r.json())
      .then(d => {
        const ids = Array.isArray(d) ? d.map((c: any) => c.case_id) : (d?.cases?.map((c: any) => c.case_id) || [])
        if (ids.length > 0) {
          setCases(ids)
          setSelectedCase(ids[0])
          loadData(ids[0])
        } else {
          loadData('CASE001')
        }
      })
      .catch(() => loadData('CASE001'))
  }, [])

  const loadData = async (caseId: string) => {
    setLoading(true)
    try {
      const url = caseId ? `/api/analytics/telecom?case_id=${caseId}` : '/api/analytics/telecom'
      const r = await fetch(url)
      const d = await r.json()
      setData(d)
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  const handleCaseChange = (newCase: string) => {
    setSelectedCase(newCase)
    loadData(newCase)
  }

  const summary = data?.summary || {}
  const frequentPairs: FrequentPair[] = data?.frequent_communications || []
  const connectors: HiddenConnector[] = data?.hidden_connectors || []
  const surges: TemporalSurge[] = data?.temporal_surges || []
  const locations: LocationCorrelation[] = data?.location_correlations || []
  const rawTimeline: TimelineEvent[] = data?.timeline || []
  const devices: CommonDevice[] = data?.common_devices || []

  // Filtered timeline
  const filteredTimeline = useMemo(() => {
    return rawTimeline.filter(ev => {
      if (timelineFilter !== 'ALL' && ev.event_type !== timelineFilter) return false
      if (!searchQuery) return true
      const q = searchQuery.toLowerCase()
      return (
        ev.narrative.toLowerCase().includes(q) ||
        ev.party_a?.label.toLowerCase().includes(q) ||
        ev.party_b?.label.toLowerCase().includes(q) ||
        ev.location?.name.toLowerCase().includes(q) ||
        ev.timestamp?.toLowerCase().includes(q)
      )
    })
  }, [rawTimeline, timelineFilter, searchQuery])

  // Filtered frequent communications
  const filteredPairs = useMemo(() => {
    if (!searchQuery) return frequentPairs
    const q = searchQuery.toLowerCase()
    return frequentPairs.filter(p =>
      p.party_a.label.toLowerCase().includes(q) ||
      p.party_b.label.toLowerCase().includes(q) ||
      p.explanation.toLowerCase().includes(q)
    )
  }, [frequentPairs, searchQuery])

  // Format daily surge chart
  const surgeDailyChart = useMemo(() => {
    if (surges.length > 0 && surges[0].daily_timeline) {
      return surges[0].daily_timeline
    }
    return summary.daily_distribution || []
  }, [surges, summary])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, paddingBottom: 60 }}>
      {/* Header & Case Selector */}
      <div className="glass-panel" style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <Radio size={20} color="var(--accent)" />
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
              Call Detail Record (CDR) Intelligence
            </h2>
            <span className="badge badge-accent" style={{ fontSize: 10 }}>Forensic Engine</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>
            {data?.case_title || 'Multi-source telecom & tower signal analysis'}
          </div>
        </div>

        <div style={{ flex: 1 }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--text-dim)', fontWeight: 500 }}>Select Case:</span>
          <select
            className="input-field"
            value={selectedCase}
            onChange={e => handleCaseChange(e.target.value)}
            style={{ width: 140, fontFamily: 'var(--mono)' }}
            id="cdr-case-select"
          >
            {cases.map(cid => <option key={cid} value={cid}>{cid}</option>)}
          </select>
          <button
            className="btn btn-primary"
            id="cdr-refresh-btn"
            onClick={() => loadData(selectedCase)}
            disabled={loading}
          >
            {loading ? 'Analyzing…' : 'Analyze Case'}
          </button>
        </div>
      </div>

      {/* KPI Ribbon */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
        <div className="glass-panel" style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Calls</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-bright)', marginTop: 4 }}>
            {summary.total_calls || 0}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2, display: 'flex', gap: 6 }}>
            <span>📞 {summary.voice_calls || 0} voice</span>
            <span>•</span>
            <span>💬 {summary.sms_calls || 0} sms</span>
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Call Duration</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#38bdf8', marginTop: 4 }}>
            {summary.total_duration_formatted || '0s'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
            Cumulative talk time
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Frequent Pairs (A ↔ B)</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#f59e0b', marginTop: 4 }}>
            {frequentPairs.length}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
            High-frequency links
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Hidden Connectors</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#ec4899', marginTop: 4 }}>
            {connectors.length}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
            Bridge / broker nodes
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Co-Locations</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#10b981', marginTop: 4 }}>
            {locations.length}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
            Tower rendezvous points
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '12px 16px' }}>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Burner Handsets</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#ef4444', marginTop: 4 }}>
            {devices.length}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
            Multi-SIM hardware
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
        <button
          className={tab === 'timeline' ? 'btn btn-primary' : 'btn btn-secondary'}
          onClick={() => setTab('timeline')}
          id="cdr-tab-timeline"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Clock size={14} /> ⭐ Communication Timeline ({rawTimeline.length})
        </button>
        <button
          className={tab === 'frequent' ? 'btn btn-primary' : 'btn btn-secondary'}
          onClick={() => setTab('frequent')}
          id="cdr-tab-frequent"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <ArrowLeftRight size={14} /> Frequent Pairs A ↔ B ({frequentPairs.length})
        </button>
        <button
          className={tab === 'connectors' ? 'btn btn-primary' : 'btn btn-secondary'}
          onClick={() => setTab('connectors')}
          id="cdr-tab-connectors"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Users size={14} /> Hidden Connectors ({connectors.length})
        </button>
        <button
          className={tab === 'temporal' ? 'btn btn-primary' : 'btn btn-secondary'}
          onClick={() => setTab('temporal')}
          id="cdr-tab-temporal"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Zap size={14} /> Pre-Incident Surges ({surges.length})
        </button>
        <button
          className={tab === 'locations' ? 'btn btn-primary' : 'btn btn-secondary'}
          onClick={() => setTab('locations')}
          id="cdr-tab-locations"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <MapPin size={14} /> Tower Co-Location ({locations.length})
        </button>
        <button
          className={tab === 'devices' ? 'btn btn-primary' : 'btn btn-secondary'}
          onClick={() => setTab('devices')}
          id="cdr-tab-devices"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Smartphone size={14} /> Burners & Hardware ({devices.length})
        </button>
      </div>

      {/* Filter / Search Bar */}
      <div className="glass-panel" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <Search size={16} color="var(--text-faint)" />
        <input
          className="input-field"
          placeholder="Filter by suspect name, phone number, cell tower, or text…"
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          style={{ flex: 1 }}
          id="cdr-search-input"
        />
        {tab === 'timeline' && (
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <Filter size={14} color="var(--text-faint)" />
            {(['ALL', 'CALL', 'SMS', 'MOVEMENT', 'INCIDENT'] as const).map(f => (
              <button
                key={f}
                className={timelineFilter === f ? 'btn btn-primary' : 'btn btn-secondary'}
                onClick={() => setTimelineFilter(f)}
                style={{ padding: '4px 10px', fontSize: 11 }}
              >
                {f}
              </button>
            ))}
          </div>
        )}
      </div>

      {loading ? (
        <div className="glass-panel" style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)' }}>
          Extracting and correlating CDR intelligence for {selectedCase}…
        </div>
      ) : (
        <>
          {/* TAB 1: KILLER FEATURE — COMMUNICATION TIMELINE */}
          {tab === 'timeline' && (
            <div className="glass-panel" style={{ padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div>
                  <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Clock size={16} color="var(--accent)" /> Unified Forensic Communication & Movement Timeline
                  </h3>
                  <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                    Chronologically mapped sequence of calls, messages, surveillance movements, and the incident anchor.
                  </div>
                </div>
                <span className="badge badge-accent" style={{ fontSize: 11 }}>
                  {filteredTimeline.length} Chronological Events
                </span>
              </div>

              {filteredTimeline.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-faint)' }}>
                  No timeline events matching the current search criteria.
                </div>
              ) : (
                <div style={{ position: 'relative', paddingLeft: 24, borderLeft: '2px solid rgba(56, 189, 248, 0.2)', maxHeight: '62vh', overflowY: 'auto', paddingRight: 10 }}>
                  {filteredTimeline.map((ev, idx) => {
                    const isIncident = ev.event_type === 'INCIDENT'
                    const isCall = ev.event_type === 'CALL'
                    const isSMS = ev.event_type === 'SMS'
                    const isMovement = ev.event_type === 'MOVEMENT'

                    const dotColor = isIncident ? '#ef4444' : isCall ? '#38bdf8' : isSMS ? '#10b981' : '#f59e0b'

                    return (
                      <div
                        key={idx}
                        style={{
                          marginBottom: 16,
                          position: 'relative',
                          padding: isIncident ? '16px 20px' : '12px 16px',
                          background: isIncident ? 'rgba(239, 68, 68, 0.08)' : 'rgba(255, 255, 255, 0.02)',
                          border: isIncident ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid var(--border)',
                          borderRadius: 8,
                        }}
                      >
                        {/* Timeline Node Point */}
                        <div
                          style={{
                            position: 'absolute',
                            left: -31,
                            top: isIncident ? 20 : 16,
                            width: isIncident ? 14 : 10,
                            height: isIncident ? 14 : 10,
                            borderRadius: '50%',
                            background: dotColor,
                            boxShadow: isIncident ? '0 0 12px #ef4444' : `0 0 6px ${dotColor}`,
                          }}
                        />

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, flexWrap: 'wrap', gap: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span
                              className="badge"
                              style={{
                                background: `${dotColor}22`,
                                color: dotColor,
                                border: `1px solid ${dotColor}44`,
                                fontSize: 10,
                                fontWeight: 700,
                              }}
                            >
                              {isIncident ? '🚨 INCIDENT' : isCall ? '📞 CALL' : isSMS ? '💬 SMS' : '🚶 MOVEMENT'}
                            </span>
                            <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text-bright)' }}>
                              {ev.timestamp?.replace('T', ' ')}
                            </span>
                            {ev.relative_time && (
                              <span
                                style={{
                                  fontSize: 10,
                                  padding: '2px 8px',
                                  borderRadius: 12,
                                  background: isIncident ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.06)',
                                  color: isIncident ? '#ef4444' : 'var(--text-faint)',
                                  fontFamily: 'var(--mono)',
                                }}
                              >
                                {ev.relative_time}
                              </span>
                            )}
                          </div>

                          {ev.location?.name && (
                            <span style={{ fontSize: 11, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 4 }}>
                              <MapPin size={12} color="var(--accent)" />
                              {ev.location.name} {ev.location.city ? `(${ev.location.city})` : ''}
                            </span>
                          )}
                        </div>

                        <div style={{ fontSize: 13, color: isIncident ? '#f87171' : 'var(--text)', fontWeight: isIncident ? 600 : 400, lineHeight: 1.5 }}>
                          {ev.narrative}
                        </div>

                        {/* Additional details for calls */}
                        {(isCall || isSMS) && ev.party_a && ev.party_b && (
                          <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, color: 'var(--text-faint)', flexWrap: 'wrap' }}>
                            <span><strong>Caller:</strong> {ev.party_a.label}</span>
                            <span><ArrowRight size={12} style={{ display: 'inline', verticalAlign: 'middle' }} /> <strong>Receiver:</strong> {ev.party_b.label}</span>
                            {ev.duration_formatted && <span><strong>Duration:</strong> {ev.duration_formatted}</span>}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: FREQUENT COMMUNICATION A <-> B */}
          {tab === 'frequent' && (
            <div className="glass-panel" style={{ padding: 20 }}>
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ArrowLeftRight size={16} color="var(--accent)" /> Frequent Communication Pairs (A ↔ B)
                </h3>
                <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                  Identifies heavy, sustained communication channels, total duration in hours, and directional symmetry.
                </div>
              </div>

              {filteredPairs.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-faint)' }}>
                  No frequent caller pairs found for this case.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: '62vh', overflowY: 'auto', paddingRight: 8 }}>
                  {filteredPairs.map((pair, i) => (
                    <div
                      key={i}
                      style={{
                        padding: 16,
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid var(--border)',
                        borderRadius: 8,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                            <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-bright)' }}>
                              {pair.party_a.person_name}
                            </span>
                            <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
                              ({pair.party_a.number})
                            </span>
                            <ArrowLeftRight size={16} color="var(--text-faint)" />
                            <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-bright)' }}>
                              {pair.party_b.person_name}
                            </span>
                            <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
                              ({pair.party_b.number})
                            </span>
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>
                            {pair.explanation}
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <span
                            className="badge"
                            style={{
                              background: `${SEV_COLOR[pair.severity]}22`,
                              color: SEV_COLOR[pair.severity],
                              fontSize: 10,
                            }}
                          >
                            {pair.severity}
                          </span>
                          <span className="badge badge-accent" style={{ fontSize: 11 }}>
                            {pair.total_calls} Calls
                          </span>
                          <span className="badge badge-default" style={{ fontSize: 11, color: '#f59e0b' }}>
                            ⏱️ {pair.total_duration_formatted}
                          </span>
                        </div>
                      </div>

                      {/* Direction and details */}
                      <div style={{ display: 'flex', gap: 20, marginTop: 12, padding: '10px 14px', background: 'rgba(0,0,0,0.2)', borderRadius: 6, fontSize: 11, color: 'var(--text-dim)', flexWrap: 'wrap' }}>
                        <span>
                          <strong>Direction Split:</strong> {pair.party_a.person_name} ({pair.a_to_b_calls}) ➔ {pair.party_b.person_name} ({pair.b_to_a_calls})
                        </span>
                        <span>
                          <strong>Modality:</strong> {pair.voice_count} Voice / {pair.sms_count} SMS
                        </span>
                        <span>
                          <strong>Avg Duration:</strong> {pair.average_duration_seconds}s
                        </span>
                        {pair.first_contact && (
                          <span>
                            <strong>Window:</strong> {pair.first_contact.slice(0, 10)} to {pair.last_contact?.slice(0, 10)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: HIDDEN CONNECTORS (A -> X, B -> X, C -> X) */}
          {tab === 'connectors' && (
            <div className="glass-panel" style={{ padding: 20 }}>
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Users size={16} color="#ec4899" /> Hidden Connector & Bridge Analysis (A → X, B → X, C → X)
                </h3>
                <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                  Detects central coordinators or handlers (X) communicating with multiple parties who exhibit zero or low direct contact with each other.
                </div>
              </div>

              {connectors.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-faint)' }}>
                  No hidden connector patterns detected for this case.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14, maxHeight: '62vh', overflowY: 'auto', paddingRight: 8 }}>
                  {connectors.map((conn, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: 18,
                        background: 'rgba(236, 72, 153, 0.04)',
                        border: '1px solid rgba(236, 72, 153, 0.25)',
                        borderRadius: 8,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 16, fontWeight: 800, color: '#f472b6' }}>
                              {conn.connector.person_name}
                            </span>
                            <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text-faint)' }}>
                              ({conn.connector.number})
                            </span>
                            <span className="badge" style={{ background: 'rgba(236,72,153,0.2)', color: '#f472b6', fontSize: 10 }}>
                              OPERATIONAL HUB / DISPATCHER
                            </span>
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 6, lineHeight: 1.5 }}>
                            {conn.explanation}
                          </div>
                        </div>

                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontSize: 20, fontWeight: 800, color: '#f472b6' }}>
                            {conn.disconnected_pairs_count}
                          </span>
                          <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Isolated Pairs Bridged</div>
                        </div>
                      </div>

                      {/* Bridged Contacts */}
                      <div style={{ marginTop: 12 }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 6 }}>
                          Connected Parties ({conn.connected_parties_count}) with {conn.disconnection_rate}% Non-Intercommunication:
                        </div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {conn.connected_parties.map((cp, pIdx) => (
                            <span
                              key={pIdx}
                              style={{
                                fontSize: 11,
                                padding: '3px 10px',
                                borderRadius: 16,
                                background: 'rgba(255,255,255,0.04)',
                                border: '1px solid var(--border)',
                                color: 'var(--text-bright)',
                              }}
                            >
                              {cp.label}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: TEMPORAL COMMUNICATION (PRE-INCIDENT SURGES) */}
          {tab === 'temporal' && (
            <div className="glass-panel" style={{ padding: 20 }}>
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Zap size={16} color="#f59e0b" /> Temporal Communication & Pre-Incident Escalation
                </h3>
                <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                  Detects sharp spikes in communication volume leading up to the incident date.
                </div>
              </div>

              {surges.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {surges.map((s, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: 16,
                        background: 'rgba(245, 158, 11, 0.08)',
                        border: '1px solid rgba(245, 158, 11, 0.3)',
                        borderRadius: 8,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <div style={{ fontSize: 16, fontWeight: 800, color: '#f59e0b' }}>
                            ⚡ {s.surge_multiplier}x Communication Surge Detected
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>
                            Incident Date: <strong>{s.incident_date}</strong> • Baseline: {s.baseline_daily_average} calls/day ➔ Surge: {s.pre_incident_daily_average} calls/day
                          </div>
                        </div>
                        <span className="badge" style={{ background: 'rgba(245,158,11,0.2)', color: '#f59e0b', fontSize: 11 }}>
                          {s.total_surge_calls} Calls in Surge Window
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 10, lineHeight: 1.6 }}>
                        {s.explanation}
                      </div>
                    </div>
                  ))}

                  {/* Chart */}
                  <div style={{ height: 220, marginTop: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginBottom: 8 }}>
                      Daily Telecom Activity & Run-Up Trend:
                    </div>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={surgeDailyChart}>
                        <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <Tooltip contentStyle={{ background: '#141d33', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, color: '#f1f5f9', fontSize: 12 }} />
                        <Bar dataKey="calls" fill="#f59e0b" radius={[4, 4, 0, 0]} name="Calls / Events" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : (
                <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-faint)' }}>
                  No significant pre-incident surge detected for this case.
                </div>
              )}
            </div>
          )}

          {/* TAB 5: LOCATION CORRELATION (TOWER CO-LOCATION) */}
          {tab === 'locations' && (
            <div className="glass-panel" style={{ padding: 20 }}>
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <MapPin size={16} color="#10b981" /> Cell Tower Location Correlation & Co-Location
                </h3>
                <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                  Detects distinct suspect phones simultaneously active at the same cell tower within the same time window.
                </div>
              </div>

              {locations.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-faint)' }}>
                  No multi-phone cell tower co-locations identified for this case.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: '62vh', overflowY: 'auto', paddingRight: 8 }}>
                  {locations.map((loc, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: 16,
                        background: 'rgba(16, 185, 129, 0.04)',
                        border: '1px solid rgba(16, 185, 129, 0.2)',
                        borderRadius: 8,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 15, fontWeight: 700, color: '#10b981' }}>
                              📍 {loc.tower_name} ({loc.tower_id})
                            </span>
                            <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                              {loc.area}, {loc.city}
                            </span>
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 6 }}>
                            {loc.explanation}
                          </div>
                        </div>

                        <div style={{ textAlign: 'right' }}>
                          <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', fontSize: 11 }}>
                            {loc.distinct_entities_count} Suspects Present
                          </span>
                          <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 4, fontFamily: 'var(--mono)' }}>
                            {loc.timestamp_window}
                          </div>
                        </div>
                      </div>

                      {/* Suspects list */}
                      <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {loc.entities.map((p, pIdx) => (
                          <span
                            key={pIdx}
                            style={{
                              fontSize: 11,
                              padding: '2px 8px',
                              borderRadius: 4,
                              background: 'rgba(255, 255, 255, 0.04)',
                              color: 'var(--text-bright)',
                              border: '1px solid var(--border)',
                            }}
                          >
                            👤 {p.label}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 6: BURNERS & HARDWARE */}
          {tab === 'devices' && (
            <div className="glass-panel" style={{ padding: 20 }}>
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Smartphone size={16} color="#ef4444" /> Burner Devices & Shared Hardware
                </h3>
                <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 2 }}>
                  Detects IMEI handsets operated with multiple SIM cards or shared across distinct criminal profiles.
                </div>
              </div>

              {devices.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-faint)' }}>
                  No multi-SIM burner devices recorded for this case.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: '62vh', overflowY: 'auto', paddingRight: 8 }}>
                  {devices.map((dev, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: 16,
                        background: 'rgba(239, 68, 68, 0.04)',
                        border: '1px solid rgba(239, 68, 68, 0.25)',
                        borderRadius: 8,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 15, fontWeight: 700, color: '#ef4444' }}>
                              📱 {dev.make} {dev.model}
                            </span>
                            <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text-faint)' }}>
                              IMEI: {dev.imei}
                            </span>
                            <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', fontSize: 10 }}>
                              BURNER HANDSET
                            </span>
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 6 }}>
                            {dev.explanation}
                          </div>
                        </div>

                        <span className="badge badge-default" style={{ fontSize: 11 }}>
                          {dev.sim_count} SIM Cards
                        </span>
                      </div>

                      {dev.associated_persons.length > 0 && (
                        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-dim)' }}>
                          <strong>Associated Suspect Profiles:</strong> {dev.associated_persons.join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
