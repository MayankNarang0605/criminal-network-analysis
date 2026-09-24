// Cases View — filterable table + FIR drawer
import React, { useState, useEffect } from 'react'
import { FolderKanban, Filter, ChevronRight, ChevronDown, AlertTriangle, CheckCircle2, Clock, FileText, Search, X } from 'lucide-react'

interface Case {
  case_id: string
  case_title: string
  crime_type: string
  date_range_start: string
  date_range_end: string
  primary_location: string
  difficulty: string
  topology: string
  n_network_entities: number
}

interface FIR {
  fir_id: string
  fir_number: string
  police_station_id: string
  registration_date: string
  crime_type: string
  incident_city: string
  incident_area: string
  status: string
  summary: string
}

const DIFFICULTY_COLORS: Record<string, string> = {
  Basic: 'var(--green)',
  Intermediate: 'var(--accent)',
  Advanced: 'var(--amber)',
  Expert: 'var(--red)',
}

export default function CasesView() {
  const [cases, setCases] = useState<Case[]>([])
  const [filtered, setFiltered] = useState<Case[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [diffFilter, setDiffFilter] = useState('')
  const [crimeFilter, setCrimeFilter] = useState('')
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)
  const [firs, setFirs] = useState<FIR[]>([])
  const [firLoading, setFirLoading] = useState(false)

  useEffect(() => {
    fetch('/api/cases?limit=100')
      .then(r => r.json())
      .then(d => {
        const list = Array.isArray(d) ? d : (d.cases || [])
        setCases(list)
        setFiltered(list)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    let result = cases
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(c =>
        c.case_id.toLowerCase().includes(q) ||
        c.case_title.toLowerCase().includes(q) ||
        c.crime_type.toLowerCase().includes(q) ||
        c.primary_location?.toLowerCase().includes(q)
      )
    }
    if (diffFilter) result = result.filter(c => c.difficulty === diffFilter)
    if (crimeFilter) result = result.filter(c => c.crime_type === crimeFilter)
    setFiltered(result)
  }, [search, diffFilter, crimeFilter, cases])

  const openCase = async (c: Case) => {
    setSelectedCase(c)
    setFirLoading(true)
    try {
      const r = await fetch(`/api/cases/${c.case_id}/firs`)
      const d = await r.json()
      setFirs(Array.isArray(d) ? d : (d.firs || []))
    } catch {
      setFirs([])
    } finally {
      setFirLoading(false)
    }
  }

  const crimes = [...new Set(cases.map(c => c.crime_type).filter(Boolean))]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header + Filters */}
      <div className="glass-panel" style={{ padding: '14px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <FolderKanban size={18} color="var(--accent)" />
          <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
            Case Management — {filtered.length} / {cases.length} Cases
          </h2>
          <div style={{ flex: 1 }} />
          {/* Search */}
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)' }} />
            <input
              className="input-field"
              style={{ paddingLeft: 32, width: 220 }}
              placeholder="Search cases..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              id="case-search-input"
            />
          </div>
          {/* Difficulty filter */}
          <select id="case-diff-filter" className="input-field" style={{ width: 140 }} value={diffFilter} onChange={e => setDiffFilter(e.target.value)}>
            <option value="">All Difficulties</option>
            {['Basic', 'Intermediate', 'Advanced', 'Expert'].map(d => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
          {/* Crime filter */}
          <select id="case-crime-filter" className="input-field" style={{ width: 160 }} value={crimeFilter} onChange={e => setCrimeFilter(e.target.value)}>
            <option value="">All Crime Types</option>
            {crimes.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {(search || diffFilter || crimeFilter) && (
            <button className="btn btn-ghost" onClick={() => { setSearch(''); setDiffFilter(''); setCrimeFilter('') }}>
              <X size={14} /> Clear
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selectedCase ? '1fr 420px' : '1fr', gap: 16 }}>
        {/* Cases Table */}
        <div className="glass-panel" style={{ overflow: 'hidden' }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)' }}>Loading cases…</div>
          ) : (
            <div style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 220px)' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Case ID', 'Title', 'Crime Type', 'Difficulty', 'Entities', 'Location', 'Status'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c, i) => (
                    <tr
                      key={c.case_id}
                      id={`case-row-${c.case_id}`}
                      onClick={() => openCase(c)}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        cursor: 'pointer',
                        background: selectedCase?.case_id === c.case_id ? 'rgba(0,210,255,0.06)' : i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                        transition: 'background 0.15s',
                      }}
                      className="table-row-hover"
                    >
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--accent)' }}>{c.case_id}</span>
                      </td>
                      <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.case_title}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <span className="badge badge-default" style={{ fontSize: 11 }}>{c.crime_type}</span>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: DIFFICULTY_COLORS[c.difficulty] || 'var(--text-faint)' }}>{c.difficulty}</span>
                      </td>
                      <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-dim)', textAlign: 'center' }}>{c.n_network_entities}</td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text-faint)' }}>{c.primary_location || '—'}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
                          <Clock size={12} color="var(--amber)" /> Active
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && (
                <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-faint)' }}>No cases match your filters.</div>
              )}
            </div>
          )}
        </div>

        {/* Case Detail Drawer */}
        {selectedCase && (
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: 0, overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--accent)' }}>{selectedCase.case_id}</span>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>{selectedCase.case_title}</div>
              </div>
              <button className="btn btn-ghost" onClick={() => setSelectedCase(null)} id="close-case-drawer"><X size={16} /></button>
            </div>

            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              <span className="badge badge-accent">{selectedCase.difficulty}</span>
              <span className="badge badge-default">{selectedCase.crime_type}</span>
              <span className="badge badge-default">{selectedCase.topology}</span>
              <span className="badge badge-default">{selectedCase.n_network_entities} entities</span>
            </div>

            <div style={{ padding: '12px 18px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Date Range</div>
              <div style={{ fontSize: 12, color: 'var(--text)' }}>{selectedCase.date_range_start} → {selectedCase.date_range_end}</div>
            </div>

            {/* FIRs */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '14px 18px' }}>
              <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: 6 }}>
                <FileText size={12} /> First Information Reports
              </div>
              {firLoading ? (
                <div style={{ color: 'var(--text-faint)', fontSize: 13 }}>Loading FIRs…</div>
              ) : firs.length === 0 ? (
                <div style={{ color: 'var(--text-faint)', fontSize: 13 }}>No FIRs found.</div>
              ) : (
                firs.map(fir => (
                  <div key={fir.fir_id} style={{ padding: '12px 14px', background: 'rgba(255,255,255,0.02)', borderRadius: 8, marginBottom: 10, border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)' }}>{fir.fir_number}</span>
                      <span className={`badge ${fir.status === 'Open' ? 'badge-accent' : 'badge-default'}`} style={{ fontSize: 10 }}>{fir.status}</span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 4 }}>{fir.incident_city} — {fir.incident_area}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-faint)', lineHeight: 1.5 }}>{fir.summary?.slice(0, 150)}…</div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
