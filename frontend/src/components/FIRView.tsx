// FIR & Document Intelligence View — High-precision NER, entity extraction, official FIR metadata, and crime classification
import React, { useState, useEffect, useMemo } from 'react'
import {
  FileSearch,
  Brain,
  Tag,
  ChevronRight,
  FileText,
  Zap,
  MapPin,
  Car,
  Phone,
  User,
  Building,
  Calendar,
  DollarSign,
  Shield,
  AlertTriangle,
  ExternalLink,
  Clock,
  Sparkles,
  Filter,
} from 'lucide-react'

interface NEREntity {
  text: string
  label: string
  entity_id?: string
  start: number
  end: number
  confidence?: number
}

interface DocResult {
  doc_id: string
  filename: string
  document_type: string
  char_count: number
  full_text: string
  preview: string
  ner: {
    method: string
    entity_count: number
    entities: NEREntity[]
  }
  crime_classification: {
    predicted_crime_type: string
    confidence: number
    method: string
    top_predictions: Array<{ label: string; score: number }>
  }
}

interface OfficialFIRMeta {
  fir_id: string
  fir_number: string
  police_station_id: string
  registration_date: string
  incident_date: string
  incident_city: string
  incident_area?: string
  crime_type: string
  complainant_id?: string
  summary: string
  status: string
}

interface CaseNLPResult {
  case_id: string
  documents_found: number
  official_fir?: OfficialFIRMeta
  results: DocResult[]
  entity_summary: Record<string, string[]>
}

const LABEL_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  PERSON: { bg: 'rgba(59, 130, 246, 0.15)', text: '#60a5fa', border: 'rgba(59, 130, 246, 0.4)' },
  ORG: { bg: 'rgba(139, 92, 246, 0.15)', text: '#c084fc', border: 'rgba(139, 92, 246, 0.4)' },
  GPE: { bg: 'rgba(16, 185, 129, 0.15)', text: '#34d399', border: 'rgba(16, 185, 129, 0.4)' },
  LOC: { bg: 'rgba(236, 72, 153, 0.15)', text: '#f472b6', border: 'rgba(236, 72, 153, 0.4)' },
  VEHICLE: { bg: 'rgba(245, 158, 11, 0.15)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.4)' },
  VEHICLE_MENTION: { bg: 'rgba(245, 158, 11, 0.12)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.3)' },
  PHONE: { bg: 'rgba(16, 185, 129, 0.15)', text: '#34d399', border: 'rgba(16, 185, 129, 0.4)' },
  DATE: { bg: 'rgba(234, 179, 8, 0.15)', text: '#facc15', border: 'rgba(234, 179, 8, 0.4)' },
  MONEY: { bg: 'rgba(6, 182, 212, 0.15)', text: '#22d3ee', border: 'rgba(6, 182, 212, 0.4)' },
  CASE_ID: { bg: 'rgba(0, 210, 255, 0.15)', text: '#38bdf8', border: 'rgba(0, 210, 255, 0.4)' },
  FIR_REF: { bg: 'rgba(99, 102, 241, 0.15)', text: '#818cf8', border: 'rgba(99, 102, 241, 0.4)' },
  LEGAL_SECTION: { bg: 'rgba(239, 68, 68, 0.15)', text: '#f87171', border: 'rgba(239, 68, 68, 0.4)' },
  MODUS_OPERANDI: { bg: 'rgba(244, 63, 94, 0.15)', text: '#fb7185', border: 'rgba(244, 63, 94, 0.4)' },
}

export default function FIRView() {
  const [cases, setCases] = useState<string[]>([])
  const [selectedCase, setSelectedCase] = useState('CASE001')
  const [result, setResult] = useState<CaseNLPResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState<DocResult | null>(null)
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string>('ALL')
  const [selectedEntityFocus, setSelectedEntityFocus] = useState<NEREntity | null>(null)

  // Fetch available cases on mount
  useEffect(() => {
    fetch('/api/nlp/cases')
      .then(r => r.json())
      .then(d => {
        const cList = d.cases || []
        setCases(cList)
        if (cList.length > 0 && !selectedCase) {
          setSelectedCase(cList[0])
        }
      })
      .catch(() => {})
  }, [])

  const processCase = async (caseId: string) => {
    if (!caseId) return
    setSelectedCase(caseId)
    setSelectedDoc(null)
    setSelectedEntityFocus(null)
    setLoading(true)
    try {
      const r = await fetch(`/api/nlp/extract/${caseId}`)
      const d = await r.json()
      setResult(d)
      if (d.results?.length > 0) {
        setSelectedDoc(d.results[0])
      }
    } catch {
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  // Load default case on initial render
  useEffect(() => {
    if (selectedCase) {
      processCase(selectedCase)
    }
  }, [selectedCase])

  // Filtered entities for currently selected document
  const filteredDocEntities = useMemo(() => {
    if (!selectedDoc) return []
    const ents = selectedDoc.ner.entities || []
    if (activeCategoryFilter === 'ALL') return ents
    return ents.filter(e => e.label === activeCategoryFilter)
  }, [selectedDoc, activeCategoryFilter])

  // Render text with interactive inline highlights
  const renderedHighlightedText = useMemo(() => {
    if (!selectedDoc) return null
    const text = selectedDoc.full_text || selectedDoc.preview || ''
    const entities = [...(selectedDoc.ner.entities || [])].sort((a, b) => a.start - b.start)

    if (entities.length === 0) {
      return <span>{text}</span>
    }

    const segments: React.ReactNode[] = []
    let cursor = 0

    entities.forEach((ent, idx) => {
      // Un-highlighted text before entity
      if (ent.start > cursor) {
        segments.push(
          <span key={`plain-${cursor}`}>
            {text.slice(cursor, ent.start)}
          </span>
        )
      }

      // Highlighted entity tag
      if (ent.start >= cursor && ent.end <= text.length) {
        const theme = LABEL_COLORS[ent.label] || { bg: 'rgba(255,255,255,0.1)', text: '#f1f5f9', border: 'rgba(255,255,255,0.2)' }
        const isFocused = selectedEntityFocus && selectedEntityFocus.text === ent.text && selectedEntityFocus.label === ent.label

        segments.push(
          <mark
            key={`ent-${idx}-${ent.start}`}
            onClick={() => setSelectedEntityFocus(ent)}
            style={{
              background: isFocused ? 'rgba(0, 210, 255, 0.35)' : theme.bg,
              color: isFocused ? '#ffffff' : theme.text,
              border: `1px solid ${isFocused ? 'var(--accent)' : theme.border}`,
              borderRadius: 4,
              padding: '1px 5px',
              margin: '0 2px',
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              boxShadow: isFocused ? '0 0 12px rgba(0,210,255,0.4)' : 'none',
              transition: 'all 0.15s ease',
            }}
            title={`${ent.label} (Click to inspect)`}
          >
            <span>{text.slice(ent.start, ent.end)}</span>
            <span
              style={{
                fontSize: 9,
                padding: '0 3px',
                borderRadius: 2,
                background: 'rgba(0,0,0,0.3)',
                color: theme.text,
                fontFamily: 'var(--mono)',
                textTransform: 'uppercase',
              }}
            >
              {ent.label}
            </span>
          </mark>
        )
        cursor = ent.end
      }
    })

    if (cursor < text.length) {
      segments.push(
        <span key={`plain-end`}>
          {text.slice(cursor)}
        </span>
      )
    }

    return segments
  }, [selectedDoc, selectedEntityFocus])

  // Count entities by category in the active document
  const entityCountsByType = useMemo(() => {
    if (!selectedDoc) return {}
    const counts: Record<string, number> = {}
    selectedDoc.ner.entities.forEach(e => {
      counts[e.label] = (counts[e.label] || 0) + 1
    })
    return counts
  }, [selectedDoc])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: 'calc(100vh - 100px)' }}>
      {/* Top Header Bar */}
      <div className="glass-panel" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0, flexWrap: 'wrap' }}>
        <Brain size={18} color="var(--accent)" />
        <div>
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)' }}>
            FIR & Document Intelligence
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-faint)', marginLeft: 8 }}>
            Lexicon-Augmented NER & Forensic Classification
          </span>
        </div>

        <div style={{ flex: 1 }} />

        {/* Case Selector */}
        <span style={{ fontSize: 12, color: 'var(--text-dim)', fontWeight: 600 }}>Select Case:</span>
        <select
          className="input-field"
          value={selectedCase}
          onChange={e => processCase(e.target.value)}
          style={{ width: 150, fontFamily: 'var(--mono)', fontWeight: 600, fontSize: 12 }}
          id="fir-case-select"
        >
          {cases.map(c => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        <button
          className="btn btn-secondary"
          onClick={() => processCase(selectedCase)}
          disabled={loading}
          style={{ padding: '6px 12px', fontSize: 12 }}
        >
          {loading ? 'Analyzing…' : '↻ Re-Analyze'}
        </button>

        {result && (
          <span className="badge badge-accent" style={{ fontSize: 11 }}>
            {result.documents_found} {result.documents_found === 1 ? 'Document' : 'Documents'} Extracted
          </span>
        )}
      </div>

      {result && result.documents_found > 0 ? (
        <div style={{ display: 'flex', gap: 12, flex: 1, minHeight: 0 }}>
          {/* Main Left Section: Official FIR Card + Document Viewer */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
            {/* Official FIR Registry Details Card */}
            {result.official_fir && (
              <div
                className="glass-panel"
                style={{
                  padding: 16,
                  borderLeft: '4px solid var(--accent)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Shield size={16} color="var(--accent)" />
                      <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Official Police FIR Record
                      </span>
                      <span className="badge badge-default" style={{ fontSize: 10, fontFamily: 'var(--mono)' }}>
                        {result.official_fir.fir_number}
                      </span>
                      <span className="badge badge-accent" style={{ fontSize: 10 }}>
                        {result.official_fir.status}
                      </span>
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-bright)', marginTop: 4 }}>
                      FIR {result.official_fir.fir_id} — {result.official_fir.crime_type}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>Registered Police Station</div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-bright)', fontFamily: 'var(--mono)' }}>
                      {result.official_fir.police_station_id}
                    </div>
                  </div>
                </div>

                {/* Key FIR Metadata Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, background: 'rgba(255,255,255,0.02)', padding: 10, borderRadius: 8, border: '1px solid var(--border)' }}>
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Incident Date</div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-bright)' }}>{result.official_fir.incident_date}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Registration Date</div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-bright)' }}>{result.official_fir.registration_date}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Incident Location</div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-bright)' }}>
                      {result.official_fir.incident_area ? `${result.official_fir.incident_area}, ` : ''}{result.official_fir.incident_city}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Complainant / Victim</div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                      {result.official_fir.complainant_id || 'Confidential'}
                    </div>
                  </div>
                </div>

                {/* Narrative Summary from Police File */}
                <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6, background: 'rgba(0,0,0,0.2)', padding: 10, borderRadius: 6 }}>
                  <strong style={{ color: 'var(--text-bright)' }}>Police Narrative Summary: </strong>
                  {result.official_fir.summary}
                </div>
              </div>
            )}

            {/* Document Selection Tabs */}
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: 'var(--text-faint)', fontWeight: 600 }}>Case Documents:</span>
              {result.results.map(doc => (
                <button
                  key={doc.doc_id}
                  className={`btn ${selectedDoc?.doc_id === doc.doc_id ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ fontSize: 11, padding: '5px 12px', display: 'flex', alignItems: 'center', gap: 6 }}
                  onClick={() => {
                    setSelectedDoc(doc)
                    setSelectedEntityFocus(null)
                  }}
                >
                  <FileText size={12} />
                  <span>{doc.filename}</span>
                  <span className="badge badge-default" style={{ fontSize: 9, padding: '1px 5px' }}>
                    {doc.ner.entity_count}
                  </span>
                </button>
              ))}
            </div>

            {/* Interactive Document Viewer with Highlighted Entities */}
            {selectedDoc && (
              <div className="glass-panel" style={{ padding: 16, flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <FileText size={16} color="var(--accent)" />
                      <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-bright)' }}>
                        {selectedDoc.filename}
                      </span>
                      <span className="badge badge-accent" style={{ fontSize: 10 }}>
                        {selectedDoc.document_type}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 2 }}>
                      {selectedDoc.char_count} characters • {selectedDoc.ner.entity_count} entities extracted via {selectedDoc.ner.method}
                    </div>
                  </div>

                  {/* Crime Classification Badge */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(255,255,255,0.03)', padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)' }}>
                    <div>
                      <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Predicted Category</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)' }}>
                        {selectedDoc.crime_classification.predicted_crime_type}
                      </div>
                    </div>
                    <span className="badge badge-accent" style={{ fontSize: 11 }}>
                      {Math.round(selectedDoc.crime_classification.confidence * 100)}%
                    </span>
                  </div>
                </div>

                {/* Full Highlighted Document Viewport */}
                <div
                  style={{
                    fontSize: 13,
                    lineHeight: 2.0,
                    color: 'var(--text)',
                    background: 'rgba(0,0,0,0.3)',
                    padding: 18,
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    fontFamily: 'var(--font)',
                    whiteSpace: 'pre-wrap',
                    minHeight: 220,
                  }}
                >
                  {renderedHighlightedText}
                </div>

                <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>
                  💡 Tip: Click any highlighted entity chip above to inspect its forensic metadata in the right panel.
                </div>
              </div>
            )}
          </div>

          {/* Right Inspector: Extracted Intelligence Breakdown */}
          <div style={{ width: 380, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
            {/* Entity Filter Chips */}
            <div className="glass-panel" style={{ padding: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                <Filter size={12} />
                <span>Entity Category Filters</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                <button
                  className={`btn ${activeCategoryFilter === 'ALL' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ padding: '3px 8px', fontSize: 10 }}
                  onClick={() => setActiveCategoryFilter('ALL')}
                >
                  All ({selectedDoc?.ner.entity_count || 0})
                </button>
                {selectedDoc &&
                  Object.entries(entityCountsByType).map(([cat, count]) => (
                    <button
                      key={cat}
                      className={`btn ${activeCategoryFilter === cat ? 'btn-primary' : 'btn-ghost'}`}
                      style={{ padding: '3px 8px', fontSize: 10 }}
                      onClick={() => setActiveCategoryFilter(cat)}
                    >
                      {cat} ({count})
                    </button>
                  ))}
              </div>
            </div>

            {/* Focused Entity Inspector Card */}
            {selectedEntityFocus && (
              <div className="glass-panel" style={{ padding: 14, borderLeft: '4px solid var(--accent)' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', marginBottom: 4 }}>
                  Selected Entity Highlight
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-bright)' }}>
                  {selectedEntityFocus.text}
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                  <span className="badge badge-accent" style={{ fontSize: 10 }}>
                    {selectedEntityFocus.label}
                  </span>
                  {selectedEntityFocus.entity_id && (
                    <span className="badge badge-default" style={{ fontSize: 10, fontFamily: 'var(--mono)' }}>
                      ID: {selectedEntityFocus.entity_id}
                    </span>
                  )}
                  {selectedEntityFocus.confidence && (
                    <span className="badge badge-default" style={{ fontSize: 10 }}>
                      {Math.round(selectedEntityFocus.confidence * 100)}% Conf
                    </span>
                  )}
                  <span className="badge badge-default" style={{ fontSize: 10, fontFamily: 'var(--mono)' }}>
                    Pos: {selectedEntityFocus.start}:{selectedEntityFocus.end}
                  </span>
                </div>
              </div>
            )}

            {/* Extracted Entities List */}
            <div className="glass-panel" style={{ padding: 14, flex: 1, display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 380, overflowY: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-bright)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Extracted Entities ({filteredDocEntities.length})
                </div>
                <span className="badge badge-default" style={{ fontSize: 10 }}>
                  {activeCategoryFilter}
                </span>
              </div>

              {filteredDocEntities.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--text-faint)', textAlign: 'center', padding: 16 }}>
                  No entities match the selected category filter.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {filteredDocEntities.map((ent, i) => {
                    const theme = LABEL_COLORS[ent.label] || { bg: 'rgba(255,255,255,0.1)', text: '#f1f5f9', border: 'rgba(255,255,255,0.2)' }
                    const isFocused = selectedEntityFocus && selectedEntityFocus.text === ent.text && selectedEntityFocus.label === ent.label

                    return (
                      <div
                        key={`${ent.text}-${i}`}
                        onClick={() => setSelectedEntityFocus(ent)}
                        style={{
                          background: isFocused ? 'rgba(0, 210, 255, 0.12)' : 'rgba(255,255,255,0.02)',
                          border: `1px solid ${isFocused ? 'var(--accent)' : 'var(--border)'}`,
                          borderRadius: 6,
                          padding: '8px 10px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)' }}>
                            {ent.text}
                          </div>
                          {ent.entity_id && (
                            <div style={{ fontSize: 10, color: 'var(--text-faint)', fontFamily: 'var(--mono)' }}>
                              Linked ID: {ent.entity_id}
                            </div>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span
                            className="badge"
                            style={{
                              background: theme.bg,
                              color: theme.text,
                              border: `1px solid ${theme.border}`,
                              fontSize: 10,
                              fontWeight: 700,
                            }}
                          >
                            {ent.label}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Crime Classification Forensic Breakdown */}
            {selectedDoc && (
              <div className="glass-panel" style={{ padding: 14 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Zap size={12} color="var(--accent)" />
                  <span>Forensic Classification Scores</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {selectedDoc.crime_classification.top_predictions?.map((p, i) => (
                    <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                        <span style={{ color: i === 0 ? 'var(--accent)' : 'var(--text-dim)', fontWeight: i === 0 ? 600 : 400 }}>
                          {p.label}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-faint)' }}>
                          {Math.round(p.score * 100)}%
                        </span>
                      </div>
                      <div style={{ height: 4, width: '100%', background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
                        <div
                          style={{
                            height: '100%',
                            width: `${Math.min(100, Math.max(5, Math.round(p.score * 100)))}%`,
                            background: i === 0 ? 'var(--accent)' : 'var(--border-strong)',
                            borderRadius: 2,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 8 }}>
                  Algorithm: {selectedDoc.crime_classification.method}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="glass-panel" style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)', flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div>
            <FileSearch size={40} color="var(--text-faint)" style={{ marginBottom: 12 }} />
            <div style={{ fontSize: 14 }}>
              {loading ? 'Running NER extraction and crime classification…' : 'Select a case above to analyze its FIR and witness documents.'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
