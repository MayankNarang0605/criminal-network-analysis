// Reports View — Full Court-Ready Investigation & Prosecution Dossier
import React, { useState, useEffect, useMemo } from 'react'
import {
  FileText, Download, Printer, ChevronRight, Shield, AlertTriangle,
  Scale, CheckSquare, Square, Save, Edit3, UserCheck, History,
  Settings2, Activity, CreditCard, Phone, MapPin, Lock, CheckCircle2,
  Sparkles, RefreshCw, Layers, Clock, AlertCircle, FileCheck, Award
} from 'lucide-react'

interface CaseItem {
  case_id: string
  case_title: string
  crime_type: string
  primary_location?: string
  n_network_entities?: number
}

interface ReportSectionsConfig {
  overview: boolean
  fir: boolean
  suspects: boolean
  network: boolean
  financial: boolean
  cdr: boolean
  geospatial: boolean
  anomalies: boolean
  timeline: boolean
  ai_summary: boolean
  conclusion: boolean
  certificate: boolean
  notes: boolean
}

export default function ReportsView() {
  const [caseList, setCaseList] = useState<CaseItem[]>([])
  const [selectedCaseId, setSelectedCaseId] = useState('CASE001')
  const [report, setReport] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [savingNotes, setSavingNotes] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null)

  // Officer customization & notes state
  const [officerName, setOfficerName] = useState('Investigating Officer (DSP / Inspector)')
  const [badgeNumber, setBadgeNumber] = useState('POL-IND-8842')
  const [stationUnit, setStationUnit] = useState('Central Crime Investigation Department / Cyber Cell')
  const [officerNotes, setOfficerNotes] = useState('')
  const [reportVersion, setReportVersion] = useState('v1.0')
  const [reportStatus, setReportStatus] = useState<'DRAFT' | 'FINAL'>('FINAL')
  const [reportScope, setReportScope] = useState<'FULL' | 'SUSPECT' | 'FINANCIAL_NETWORK'>('FULL')
  const [isEditingMetadata, setIsEditingMetadata] = useState(false)

  // Section toggle configuration
  const [sections, setSections] = useState<ReportSectionsConfig>({
    overview: true,
    fir: true,
    suspects: true,
    network: true,
    financial: true,
    cdr: true,
    geospatial: true,
    anomalies: true,
    timeline: true,
    ai_summary: true,
    conclusion: true,
    certificate: true,
    notes: true,
  })

  // 1. Fetch available cases catalog
  useEffect(() => {
    fetch('/api/cases?limit=100')
      .then(r => r.json())
      .then(data => {
        const list = Array.isArray(data) ? data : data?.cases || []
        if (list.length > 0) {
          setCaseList(list)
          setSelectedCaseId(list[0].case_id)
          loadReport(list[0].case_id)
        }
      })
      .catch(err => console.error('Failed loading cases:', err))
  }, [])

  // 2. Fetch full structured report from backend
  const loadReport = async (caseId: string) => {
    setLoading(true)
    setErrorMsg(null)
    setSaveSuccessMsg(null)
    try {
      const res = await fetch(`/api/reports/${caseId}`)
      if (!res.ok) throw new Error(`HTTP error ${res.status}`)
      const data = await res.json()
      setReport(data)
      // Initialize officer notes & metadata from report data
      if (data.officer_details) {
        setOfficerName(data.officer_details.officer_name || 'Investigating Officer (DSP / Inspector)')
        setBadgeNumber(data.officer_details.badge_number || 'POL-IND-8842')
        setStationUnit(data.officer_details.station_unit || 'Central Crime Investigation Department')
      }
      if (data.officer_notes) {
        setOfficerNotes(data.officer_notes)
      }
      if (data.version) setReportVersion(data.version)
      if (data.status) setReportStatus(data.status as any)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate investigation report')
      setReport(null)
    } finally {
      setLoading(false)
    }
  }

  // 3. Save draft notes and officer remarks
  const handleSaveNotes = async () => {
    setSavingNotes(true)
    setSaveSuccessMsg(null)
    try {
      const res = await fetch(`/api/reports/${selectedCaseId}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          officer_name: officerName,
          badge_number: badgeNumber,
          station_unit: stationUnit,
          notes: officerNotes,
          version: reportVersion,
          status: reportStatus,
        }),
      })
      if (!res.ok) throw new Error('Failed to save report customizations')
      setSaveSuccessMsg('Investigation report notes & metadata successfully saved!')
      setTimeout(() => setSaveSuccessMsg(null), 4000)
    } catch (err: any) {
      setErrorMsg(err.message || 'Error saving notes')
    } finally {
      setSavingNotes(false)
    }
  }

  // 4. Export DOCX Word Document
  const handleDownloadDocx = () => {
    const url = `/api/reports/${selectedCaseId}/export/docx?officer_name=${encodeURIComponent(officerName)}&badge_number=${encodeURIComponent(badgeNumber)}&station_unit=${encodeURIComponent(stationUnit)}&version=${encodeURIComponent(reportVersion)}&report_status=${encodeURIComponent(reportStatus)}`
    window.open(url, '_blank')
  }

  // 5. Native Print / Print-to-PDF with guaranteed multi-page rendering
  const handlePrint = () => {
    const reportElem = document.getElementById('investigation-report-document')
    if (!reportElem) {
      window.print()
      return
    }

    // Remove any lingering print frame
    const existing = document.getElementById('case-report-print-frame')
    if (existing) existing.remove()

    const iframe = document.createElement('iframe')
    iframe.id = 'case-report-print-frame'
    iframe.style.position = 'fixed'
    iframe.style.top = '-9999px'
    iframe.style.left = '-9999px'
    iframe.style.width = '1024px'
    iframe.style.height = '100%'
    iframe.style.border = '0'
    iframe.style.visibility = 'hidden'
    document.body.appendChild(iframe)

    const frameDoc = iframe.contentWindow?.document
    if (!frameDoc) {
      window.print()
      return
    }

    const printStyles = `
      @page {
        size: A4 portrait;
        margin: 12mm 14mm 14mm 14mm;
      }
      * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }
      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        font-size: 10pt;
        line-height: 1.45;
        color: #0f172a;
        background: #ffffff;
        width: 100%;
        height: auto !important;
        overflow: visible !important;
      }
      .printable-report-sheet {
        width: 100% !important;
        background: #ffffff !important;
        color: #0f172a !important;
        padding: 0 !important;
        border: none !important;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .report-section {
        page-break-inside: avoid;
        break-inside: avoid;
        margin-bottom: 20px;
        padding-bottom: 14px;
        border-bottom: 1px solid #cbd5e1;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .report-letterhead {
        page-break-after: avoid;
        break-after: avoid;
        border-bottom: 2px solid #0284c7 !important;
        padding-bottom: 12px;
        margin-bottom: 16px;
      }
      .section-title {
        font-size: 12pt;
        font-weight: 800;
        color: #0284c7 !important;
        page-break-after: avoid;
        break-after: avoid;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 9pt;
        margin-top: 6px;
        page-break-inside: auto;
      }
      tr {
        page-break-inside: avoid;
        break-inside: avoid;
      }
      th {
        background-color: #f1f5f9 !important;
        color: #1e293b !important;
        font-weight: 700;
        text-align: left;
        padding: 6px 8px;
        border: 1px solid #cbd5e1;
      }
      td {
        padding: 5px 8px;
        border: 1px solid #e2e8f0;
        color: #0f172a !important;
      }
      .badge {
        display: inline-block;
        padding: 2px 6px;
        font-size: 7.5pt;
        font-weight: 600;
        border-radius: 4px;
        border: 1px solid #94a3b8;
        background: #f8fafc !important;
        color: #0f172a !important;
      }
      div {
        border-color: #e2e8f0 !important;
      }
      [style*="background: 'rgba(255,255,255"] ,
      [style*="background: rgba(255,255,255"] ,
      [style*="background: 'var(--surface"] ,
      [style*="background: var(--surface"] {
        background: #f8fafc !important;
        border: 1px solid #e2e8f0 !important;
      }
      [style*="color: 'var(--text-bright)'"] ,
      [style*="color: var(--text-bright)"] {
        color: #0f172a !important;
      }
      [style*="color: 'var(--text-dim)'"] ,
      [style*="color: var(--text-dim)"] ,
      [style*="color: 'var(--text-faint)'"] ,
      [style*="color: var(--text-faint)"] ,
      [style*="color: 'var(--text-muted)'"] ,
      [style*="color: var(--text-muted)"] {
        color: #475569 !important;
      }
    `

    frameDoc.open()
    frameDoc.write('<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Investigation_Report_' + selectedCaseId + '</title><style>' + printStyles + '</style></head><body><div class="printable-report-sheet">' + reportElem.innerHTML + '</div></body></html>')
    frameDoc.close()

    setTimeout(() => {
      try {
        iframe.contentWindow?.focus()
        iframe.contentWindow?.print()
      } catch (e) {
        window.print()
      } finally {
        setTimeout(() => {
          if (document.body.contains(iframe)) {
            iframe.remove()
          }
        }, 3000)
      }
    }, 350)
  }

  // Toggle all sections helper
  const handleToggleAllSections = (enable: boolean) => {
    setSections({
      overview: enable,
      fir: enable,
      suspects: enable,
      network: enable,
      financial: enable,
      cdr: enable,
      geospatial: enable,
      anomalies: enable,
      timeline: enable,
      ai_summary: enable,
      conclusion: enable,
      certificate: enable,
      notes: enable,
    })
  }

  return (
    <div className="reports-view-wrapper" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      
      {/* ── Action & Controls Header Bar (Hidden during Print) ─────────────── */}
      <div className="glass-panel no-print" style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8,
              background: 'rgba(0,210,255,0.1)', border: '1px solid rgba(0,210,255,0.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Scale size={18} color="var(--accent)" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
                  Court-Ready Case Investigation Dossier
                </h2>
                <span className="badge badge-accent" style={{ fontSize: 10 }}>Section 65B Compliant</span>
                <span className={`badge ${reportStatus === 'FINAL' ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: 10 }}>
                  {reportStatus} ({reportVersion})
                </span>
              </div>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text-muted)' }}>
                Automated multi-modal forensic compilation with investigator note annotations and official DOCX / PDF export.
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            {/* Case Selector */}
            <select
              id="report-case-dropdown"
              value={selectedCaseId}
              onChange={e => {
                setSelectedCaseId(e.target.value)
                loadReport(e.target.value)
              }}
              style={{
                background: 'var(--surface-dark, #0f172a)',
                color: 'var(--text-bright, #f8fafc)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '6px 12px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                maxWidth: 240,
              }}
            >
              {caseList.map(c => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_id} — {c.case_title}
                </option>
              ))}
            </select>

            <button
              className="btn btn-secondary"
              id="report-recompute-btn"
              onClick={() => loadReport(selectedCaseId)}
              disabled={loading}
              title="Re-generate dossier"
            >
              <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
              {loading ? 'Compiling…' : 'Regenerate'}
            </button>

            <button
              className="btn btn-secondary"
              id="report-edit-officer-btn"
              onClick={() => setIsEditingMetadata(!isEditingMetadata)}
              title="Edit officer notes and signature details"
            >
              <Edit3 size={13} />
              {isEditingMetadata ? 'Hide Notes' : 'Officer Notes'}
            </button>

            <button
              className="btn btn-secondary"
              id="report-export-docx-btn"
              onClick={handleDownloadDocx}
              disabled={!report}
              title="Download Microsoft Word document"
            >
              <Download size={13} color="var(--accent)" />
              Export DOCX
            </button>

            <button
              className="btn btn-primary"
              id="report-print-pdf-btn"
              onClick={handlePrint}
              disabled={!report}
              title="Print document or Save as PDF"
            >
              <Printer size={13} />
              Print / PDF
            </button>
          </div>
        </div>

        {/* Section Toggles Drawer */}
        <div style={{
          padding: '10px 14px',
          background: 'rgba(255,255,255,0.02)',
          borderRadius: 6,
          border: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Sections to Include:
          </span>

          {[
            { id: 'overview',   label: '1. Overview' },
            { id: 'fir',        label: '2. FIRs' },
            { id: 'suspects',   label: '3. Suspects' },
            { id: 'network',    label: '4. Network' },
            { id: 'financial',  label: '5. Financial' },
            { id: 'cdr',        label: '6. CDR' },
            { id: 'geospatial', label: '7. Geospatial' },
            { id: 'anomalies',  label: '8. Anomalies' },
            { id: 'timeline',   label: '9. Timeline' },
            { id: 'ai_summary', label: '10. AI Leads' },
            { id: 'conclusion', label: '11. Conclusion' },
            { id: 'certificate',label: '12. Section 65B' },
            { id: 'notes',      label: '13. Notes' },
          ].map(sec => (
            <label key={sec.id} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 11, color: sections[sec.id as keyof ReportSectionsConfig] ? 'var(--text-bright)' : 'var(--text-muted)' }}>
              <input
                type="checkbox"
                checked={sections[sec.id as keyof ReportSectionsConfig]}
                onChange={e => setSections({ ...sections, [sec.id]: e.target.checked })}
              />
              <span>{sec.label}</span>
            </label>
          ))}

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            <button className="btn btn-ghost btn-xs" style={{ fontSize: 10 }} onClick={() => handleToggleAllSections(true)}>Select All</button>
            <button className="btn btn-ghost btn-xs" style={{ fontSize: 10 }} onClick={() => handleToggleAllSections(false)}>Clear All</button>
          </div>
        </div>

        {/* Officer Details & Notes Editor Drawer */}
        {isEditingMetadata && (
          <div style={{
            padding: '14px 18px',
            background: 'rgba(0,210,255,0.03)',
            borderRadius: 8,
            border: '1px solid rgba(0,210,255,0.2)',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <UserCheck size={15} color="var(--accent)" />
                Investigator Metadata, Versioning & Case Notes
              </span>
              <button
                className="btn btn-primary btn-xs"
                onClick={handleSaveNotes}
                disabled={savingNotes}
              >
                <Save size={12} />
                {savingNotes ? 'Saving…' : 'Save Changes'}
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
              <div>
                <label style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Investigating Officer Name</label>
                <input
                  type="text"
                  className="input-field"
                  style={{ width: '100%', fontSize: 12, marginTop: 3 }}
                  value={officerName}
                  onChange={e => setOfficerName(e.target.value)}
                />
              </div>
              <div>
                <label style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Badge / Identification No.</label>
                <input
                  type="text"
                  className="input-field"
                  style={{ width: '100%', fontSize: 12, marginTop: 3 }}
                  value={badgeNumber}
                  onChange={e => setBadgeNumber(e.target.value)}
                />
              </div>
              <div>
                <label style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Police Station / Special Unit</label>
                <input
                  type="text"
                  className="input-field"
                  style={{ width: '100%', fontSize: 12, marginTop: 3 }}
                  value={stationUnit}
                  onChange={e => setStationUnit(e.target.value)}
                />
              </div>
              <div>
                <label style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Report Version & Status</label>
                <div style={{ display: 'flex', gap: 6, marginTop: 3 }}>
                  <input
                    type="text"
                    className="input-field"
                    style={{ width: 80, fontSize: 12 }}
                    value={reportVersion}
                    onChange={e => setReportVersion(e.target.value)}
                  />
                  <select
                    className="input-field"
                    style={{ flex: 1, fontSize: 12 }}
                    value={reportStatus}
                    onChange={e => setReportStatus(e.target.value as any)}
                  >
                    <option value="DRAFT">Draft</option>
                    <option value="FINAL">Final</option>
                  </select>
                </div>
              </div>
            </div>

            <div>
              <label style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase' }}>
                Investigator Remarks, Hypothesis & Working Notes (Will appear in Section 13)
              </label>
              <textarea
                className="input-field"
                style={{ width: '100%', minHeight: 70, fontSize: 12, marginTop: 3, lineHeight: 1.5 }}
                value={officerNotes}
                onChange={e => setOfficerNotes(e.target.value)}
                placeholder="Enter investigator remarks, open evidentiary requirements, or case notes…"
              />
            </div>
          </div>
        )}

        {/* Feedback alerts */}
        {saveSuccessMsg && (
          <div style={{ padding: '8px 14px', background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 6, color: 'var(--green)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <CheckCircle2 size={14} /> {saveSuccessMsg}
          </div>
        )}
        {errorMsg && (
          <div style={{ padding: '8px 14px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6, color: 'var(--red)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertTriangle size={14} /> {errorMsg}
          </div>
        )}
      </div>

      {/* ── Printable Report Container ────────────────────────────────────────── */}
      {report ? (
        <div id="investigation-report-document" className="printable-report-sheet" style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          background: 'var(--surface, #1e293b)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '32px 36px',
        }}>
          
          {/* Official Letterhead Header */}
          <div className="report-letterhead" style={{ borderBottom: '2px solid var(--accent)', paddingBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                  STATE POLICE HEADQUARTERS • SPECIAL INVESTIGATION DIVISION
                </div>
                <h1 style={{ fontSize: 24, fontWeight: 900, color: 'var(--text-bright)', margin: '4px 0 6px' }}>
                  PROSECUTION INVESTIGATION BRIEF
                </h1>
                <div style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 700 }}>
                  Case: {report.case_title} ({report.case_id})
                </div>
              </div>

              <div style={{ textAlign: 'right', fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                <div>Report ID: <strong style={{ fontFamily: 'var(--mono)', color: 'var(--text-bright)' }}>{report.report_id}</strong></div>
                <div>Generated: <strong style={{ color: 'var(--text-bright)' }}>{report.generated_at_human}</strong></div>
                <div>Status: <span className={`badge ${reportStatus === 'FINAL' ? 'badge-success' : 'badge-warning'}`} style={{ fontSize: 9 }}>{reportStatus} ({reportVersion})</span></div>
              </div>
            </div>

            {/* Officer Identification Bar */}
            <div style={{
              marginTop: 12,
              padding: '8px 14px',
              background: 'rgba(255,255,255,0.03)',
              borderRadius: 6,
              border: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 11,
              color: 'var(--text-dim)',
              flexWrap: 'wrap',
              gap: 8,
            }}>
              <span>Investigating Officer: <strong style={{ color: 'var(--text-bright)' }}>{officerName}</strong></span>
              <span>Badge / ID: <strong style={{ color: 'var(--text-bright)', fontFamily: 'var(--mono)' }}>{badgeNumber}</strong></span>
              <span>Unit: <strong style={{ color: 'var(--text-bright)' }}>{stationUnit}</strong></span>
            </div>

            {/* Legal Advisory Banner */}
            <div style={{
              marginTop: 10,
              padding: '8px 12px',
              background: 'rgba(245,158,11,0.06)',
              border: '1px solid rgba(245,158,11,0.2)',
              borderRadius: 6,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}>
              <AlertTriangle size={14} color="#f59e0b" style={{ flexShrink: 0 }} />
              <div style={{ fontSize: 10.5, color: '#fef3c7', lineHeight: 1.4 }}>
                <strong>STATUTORY ADVISORY:</strong> This dossier compiles automated algorithmic, financial, and graph topological intelligence. Findings identify structural centrality and investigative leads — <strong>they do NOT constitute an automatic verdict of legal guilt.</strong> Formal judicial proceedings require corroboration by the investigating officer.
              </div>
            </div>
          </div>

          {/* ── 1. CASE OVERVIEW ────────────────────────────────────────────── */}
          {sections.overview && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>1.</span> Case Overview & Judicial Metadata
              </div>
              
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: 10,
                background: 'rgba(255,255,255,0.02)',
                padding: 12,
                borderRadius: 6,
                border: '1px solid var(--border)',
              }}>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Crime Classification</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>{report.case_overview.crime_type}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Primary Jurisdiction</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', marginTop: 2 }}>{report.case_overview.primary_location}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Active Date Range</div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginTop: 2 }}>
                    {report.case_overview.date_range_start} to {report.case_overview.date_range_end}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Topology & Scale</div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginTop: 2 }}>
                    {report.case_overview.topology} ({report.case_overview.total_entities} nodes)
                  </div>
                </div>
              </div>

              {/* AI Executive Summary Box */}
              <div style={{
                padding: 12,
                borderRadius: 6,
                background: 'rgba(0,210,255,0.03)',
                border: '1px solid rgba(0,210,255,0.15)',
              }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Sparkles size={13} /> Short AI-Generated Case Summary
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                  {report.case_overview.ai_summary}
                </div>
              </div>
            </section>
          )}

          {/* ── 2. FIR INTELLIGENCE ─────────────────────────────────────────── */}
          {sections.fir && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>2.</span> FIR Intelligence & Legal Accusations ({report.fir_intelligence.firs.length} FIRs)
              </div>

              {/* FIR Cards */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {report.fir_intelligence.firs.map((f: any) => (
                  <div key={f.fir_id} style={{ padding: 10, background: 'rgba(255,255,255,0.02)', borderRadius: 6, border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
                        {f.fir_number} ({f.police_station})
                      </span>
                      <span className="badge badge-default" style={{ fontSize: 10 }}>{f.status}</span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 4 }}>
                      Crime: <strong>{f.crime_type}</strong> • Incident Date: <strong>{f.incident_date}</strong> • Jurisdiction: <strong>{f.incident_city}</strong>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-faint)', lineHeight: 1.5 }}>{f.summary}</div>
                  </div>
                ))}
              </div>

              {/* Accused & Involvements Table */}
              {report.fir_intelligence.accused_entities?.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 6 }}>
                    Named Accused & Primary Suspects:
                  </div>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-faint)' }}>
                          <th style={{ padding: '6px 8px' }}>Person ID</th>
                          <th style={{ padding: '6px 8px' }}>Full Name</th>
                          <th style={{ padding: '6px 8px' }}>Alias</th>
                          <th style={{ padding: '6px 8px' }}>Alleged Role</th>
                          <th style={{ padding: '6px 8px' }}>Confidence</th>
                          <th style={{ padding: '6px 8px' }}>FIR Ref</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.fir_intelligence.accused_entities.map((a: any) => (
                          <tr key={a.person_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                            <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{a.person_id}</td>
                            <td style={{ padding: '6px 8px', fontWeight: 600, color: 'var(--text-bright)' }}>{a.full_name}</td>
                            <td style={{ padding: '6px 8px', color: 'var(--amber)' }}>{a.alias || '—'}</td>
                            <td style={{ padding: '6px 8px' }}><span className="badge badge-danger" style={{ fontSize: 9 }}>{a.role}</span></td>
                            <td style={{ padding: '6px 8px', color: 'var(--text-dim)' }}>{(a.confidence * 100).toFixed(0)}%</td>
                            <td style={{ padding: '6px 8px', color: 'var(--text-faint)' }}>{a.fir_id}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </section>
          )}

          {/* ── 3. SUSPECT PROFILES ─────────────────────────────────────────── */}
          {sections.suspects && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>3.</span> Key Suspect Profiles & Evidence-Backed Assets
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
                {report.suspect_profiles.map((s: any) => (
                  <div key={s.person_id} style={{ padding: 12, background: 'rgba(255,255,255,0.02)', borderRadius: 6, border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                          {s.full_name} {s.alias && <span style={{ color: 'var(--amber)' }}>({s.alias})</span>}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-faint)', fontFamily: 'var(--mono)' }}>{s.person_id} • {s.city} • {s.occupation}</div>
                      </div>
                      <span className="badge badge-accent" style={{ fontSize: 10 }}>
                        Score: {s.leadership_score}/100
                      </span>
                    </div>

                    <div style={{ fontSize: 10.5, color: 'var(--text-dim)', lineHeight: 1.4 }}>
                      <div>📞 Phones: <strong>{s.phones?.join(', ') || 'None recorded'}</strong></div>
                      <div>💳 Accounts: <strong>{s.bank_accounts?.length || 0} active</strong></div>
                      <div>🚗 Vehicles: <strong>{s.vehicles?.join(', ') || 'None registered'}</strong></div>
                      <div>🌐 Cross-Case Footprint: <strong>{s.cases_involved?.length || 1} cases</strong></div>
                    </div>

                    <div style={{ fontSize: 10, color: 'var(--text-faint)', borderTop: '1px dashed var(--border)', paddingTop: 4, fontStyle: 'italic' }}>
                      {s.explanation}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── 4. NETWORK ANALYSIS ─────────────────────────────────────────── */}
          {sections.network && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>4.</span> Network Topology & Leadership Scoring
              </div>

              <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                Topology Model: <strong>{report.network_analysis.case_topology}</strong> consisting of <strong>{report.network_analysis.total_nodes}</strong> entities and <strong>{report.network_analysis.total_edges}</strong> relationships (Density: {report.network_analysis.graph_density}).
              </div>

              {/* Functional Sub-Clusters */}
              {report.network_analysis.clusters_detected?.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 6 }}>
                    Identified Operational Cells / Clusters:
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8 }}>
                    {report.network_analysis.clusters_detected.map((c: any) => (
                      <div key={c.cluster_id} style={{ padding: 10, background: 'rgba(0,210,255,0.03)', borderRadius: 6, border: '1px solid rgba(0,210,255,0.15)' }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)' }}>{c.cluster_id}: {c.functional_hypothesis}</div>
                        <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 3 }}>
                          Size: {c.size} nodes • Core: {c.named_nodes?.join(', ')}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Top Leadership Table */}
              <div style={{ marginTop: 4 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 6 }}>
                  Ranked Structural Centrality Candidates:
                </div>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-faint)' }}>
                        <th style={{ padding: '6px 8px' }}>Rank</th>
                        <th style={{ padding: '6px 8px' }}>Entity</th>
                        <th style={{ padding: '6px 8px' }}>Role Classification</th>
                        <th style={{ padding: '6px 8px' }}>Leadership Score</th>
                        <th style={{ padding: '6px 8px' }}>Betweenness</th>
                        <th style={{ padding: '6px 8px' }}>Financial Vol</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.network_analysis.top_leadership_ranking.slice(0, 6).map((k: any) => (
                        <tr key={k.person_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '6px 8px', fontWeight: 700 }}>#{k.rank}</td>
                          <td style={{ padding: '6px 8px', fontWeight: 600, color: 'var(--text-bright)' }}>{k.full_name} ({k.person_id})</td>
                          <td style={{ padding: '6px 8px' }}><span className="badge badge-default" style={{ fontSize: 9 }}>{k.role_classification}</span></td>
                          <td style={{ padding: '6px 8px', fontWeight: 800, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>{k.leadership_score_100}/100</td>
                          <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)' }}>{(k.metrics?.betweenness_raw || 0).toFixed(4)}</td>
                          <td style={{ padding: '6px 8px', color: 'var(--text-dim)' }}>₹{(k.metrics?.financial_volume_inr || 0).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          )}

          {/* ── 5. FINANCIAL INTELLIGENCE ────────────────────────────────────── */}
          {sections.financial && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>5.</span> Financial Intelligence & Money Laundering Chains
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: 10,
                background: 'rgba(255,255,255,0.02)',
                padding: 12,
                borderRadius: 6,
                border: '1px solid var(--border)',
              }}>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Total Analyzed Volume</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)', marginTop: 2 }}>
                    {report.financial_intelligence.summary?.formatted_total_money || '₹0'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Suspicious Volume</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--red)', marginTop: 2 }}>
                    {report.financial_intelligence.summary?.formatted_suspicious_volume || '₹0'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Transactions Tracked</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)', marginTop: 2 }}>
                    {report.financial_intelligence.summary?.total_transactions || 0}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Flagged Mule Accounts</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--amber)', marginTop: 2 }}>
                    {report.financial_intelligence.summary?.suspicious_accounts_count || 0}
                  </div>
                </div>
              </div>

              {/* Detected Financial Patterns */}
              {report.financial_intelligence.patterns?.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {report.financial_intelligence.patterns.slice(0, 4).map((pat: any, idx: number) => (
                    <div key={idx} style={{ padding: '8px 12px', background: 'rgba(239,68,68,0.04)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)', fontSize: 11 }}>
                      <strong style={{ color: 'var(--red)' }}>{pat.pattern_type}:</strong> {pat.explanation}
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* ── 6. CDR TELECOM ANALYSIS ──────────────────────────────────────── */}
          {sections.cdr && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>6.</span> Telecom CDR & Communication Surges
              </div>

              <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                Total Records Analyzed: <strong>{report.cdr_analysis.summary?.total_calls || 0} calls</strong> ({report.cdr_analysis.summary?.total_duration_formatted || '0m'}). Distinct Callers: {report.cdr_analysis.summary?.distinct_callers || 0} • Receivers: {report.cdr_analysis.summary?.distinct_receivers || 0}.
              </div>

              {/* Frequent Communication Pairs */}
              {report.cdr_analysis.frequent_communications?.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', fontSize: 11, textAlign: 'left', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-faint)' }}>
                        <th style={{ padding: '6px 8px' }}>Caller Phone</th>
                        <th style={{ padding: '6px 8px' }}>Receiver Phone</th>
                        <th style={{ padding: '6px 8px' }}>Total Calls</th>
                        <th style={{ padding: '6px 8px' }}>Duration</th>
                        <th style={{ padding: '6px 8px' }}>Pattern Significance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.cdr_analysis.frequent_communications.slice(0, 6).map((fc: any, i: number) => {
                        const callerNum = fc.caller || fc.party_a?.number || fc.party_a?.phone_id || 'Unknown'
                        const callerName = fc.caller_name || fc.party_a?.person_name
                        const receiverNum = fc.receiver || fc.party_b?.number || fc.party_b?.phone_id || 'Unknown'
                        const receiverName = fc.receiver_name || fc.party_b?.person_name
                        const dur = fc.formatted_duration || fc.total_duration_formatted || (fc.total_duration_seconds ? `${Math.round(fc.total_duration_seconds / 60)}m` : '0m')
                        const callCount = typeof fc.total_calls === 'number' ? fc.total_calls : ((fc.a_to_b_calls || 0) + (fc.b_to_a_calls || 0))

                        return (
                          <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                            <td style={{ padding: '6px 8px' }}>
                              <div style={{ fontFamily: 'var(--mono)', color: 'var(--accent)', fontWeight: 600 }}>{callerNum}</div>
                              {callerName && <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>{callerName}</div>}
                            </td>
                            <td style={{ padding: '6px 8px' }}>
                              <div style={{ fontFamily: 'var(--mono)', color: 'var(--accent)', fontWeight: 600 }}>{receiverNum}</div>
                              {receiverName && <div style={{ fontSize: 10, color: 'var(--text-dim)' }}>{receiverName}</div>}
                            </td>
                            <td style={{ padding: '6px 8px', fontWeight: 700, color: 'var(--text-bright)' }}>{callCount} calls</td>
                            <td style={{ padding: '6px 8px', color: 'var(--text-dim)' }}>{dur}</td>
                            <td style={{ padding: '6px 8px', color: 'var(--text-faint)', fontSize: 10 }}>
                              {fc.explanation || 'Operational coordination link'}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {/* ── 7. GEOSPATIAL ANALYSIS ───────────────────────────────────────── */}
          {sections.geospatial && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>7.</span> Geospatial Analysis & Movement Corridors
              </div>

              <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                Primary Operational Base: <strong>{report.geospatial_analysis.primary_jurisdiction}</strong>. Cross-jurisdictional transit verified across: <strong>{report.geospatial_analysis.affected_cities?.join(', ') || 'Local area'}</strong> ({report.geospatial_analysis.total_sightings} physical sightings).
              </div>

              {report.geospatial_analysis.key_locations?.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8 }}>
                  {report.geospatial_analysis.key_locations.slice(0, 4).map((loc: any) => (
                    <div key={loc.location_id} style={{ padding: 8, background: 'rgba(255,255,255,0.02)', borderRadius: 6, border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-bright)' }}>{loc.name}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 2 }}>{loc.city} ({loc.type})</div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* ── 8. FORENSIC ANOMALIES ────────────────────────────────────────── */}
          {sections.anomalies && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>8.</span> Detected Forensic Anomalies & Typologies ({report.anomalies.length})
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {report.anomalies.slice(0, 6).map((an: any, i: number) => (
                  <div key={i} style={{ padding: 10, background: 'rgba(255,255,255,0.02)', borderRadius: 6, border: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)' }}>{an.title}</span>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <span className={`badge ${an.severity === 'CRITICAL' ? 'badge-danger' : 'badge-warning'}`} style={{ fontSize: 9 }}>{an.severity}</span>
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)' }}>Score: {an.anomaly_score_100}</span>
                      </div>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.4 }}>{an.what_happened}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 3 }}>Model: {an.model_used} • Detector: {an.detector_name}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── 9. UNIFIED TIMELINE ─────────────────────────────────────────── */}
          {sections.timeline && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>9.</span> Unified Chronological Forensic Timeline
              </div>

              <div style={{ position: 'relative', paddingLeft: 18, borderLeft: '2px solid var(--border)', marginLeft: 6 }}>
                {report.timeline.slice(0, 10).map((t: any, idx: number) => (
                  <div key={idx} style={{ marginBottom: 12, position: 'relative' }}>
                    <div style={{
                      position: 'absolute', left: -23, top: 3, width: 8, height: 8, borderRadius: '50%',
                      background: t.category === 'FINANCIAL' ? 'var(--accent)' : t.category === 'FIR_INCIDENT' ? 'var(--red)' : 'var(--green)'
                    }} />
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 10, color: 'var(--text-faint)', fontFamily: 'var(--mono)' }}>
                      <span>{t.timestamp}</span>
                      <span className="badge badge-default" style={{ fontSize: 8 }}>{t.category}</span>
                    </div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-bright)', marginTop: 2 }}>{t.title}</div>
                    <div style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>{t.description}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── 10. AI INVESTIGATION SUMMARY ────────────────────────────────── */}
          {sections.ai_summary && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>10.</span> AI Investigation Synthesis & Priority Leads
              </div>

              <div style={{ padding: 12, background: 'rgba(0,210,255,0.03)', borderRadius: 6, border: '1px solid rgba(0,210,255,0.15)', fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                {report.ai_investigation_summary.executive_brief}
              </div>

              <div style={{ marginTop: 4 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', marginBottom: 6 }}>
                  Recommended Actionable Leads:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {report.ai_investigation_summary.recommended_leads?.map((l: string, i: number) => (
                    <div key={i} style={{ fontSize: 11, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ color: 'var(--accent)' }}>✓</span> {l}
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* ── 11. CONCLUSION ──────────────────────────────────────────────── */}
          {sections.conclusion && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>11.</span> Conclusion & Open Evidentiary Questions
              </div>

              <div style={{ fontSize: 11.5, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                {report.conclusion.summary_verdict}
              </div>

              {report.conclusion.open_questions?.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--amber)', textTransform: 'uppercase', marginBottom: 6 }}>
                    Pending Evidentiary Gaps:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {report.conclusion.open_questions.map((q: string, i: number) => (
                      <div key={i} style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ color: 'var(--amber)' }}>?</span> {q}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          {/* ── 12. SECTION 65B CERTIFICATE ─────────────────────────────────── */}
          {sections.certificate && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--green)' }}>12.</span> Section 65B Indian Evidence Act Certificate
              </div>

              <div style={{ padding: 14, background: 'rgba(16,185,129,0.03)', borderRadius: 6, border: '1px solid rgba(16,185,129,0.2)', fontSize: 11, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span style={{ fontWeight: 700, color: 'var(--green)', fontSize: 12 }}>
                    Chain Status: {report.integrity_certificate.chain_integrity}
                  </span>
                  <span className="badge badge-success" style={{ fontSize: 10 }}>
                    {report.integrity_certificate.total_evidence_records} Records Chained
                  </span>
                </div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-faint)', wordBreak: 'break-all', marginBottom: 6 }}>
                  Merkle Root: {report.integrity_certificate.merkle_root_computed}
                </div>
                <div style={{ fontSize: 10.5, color: 'var(--text-faint)', fontStyle: 'italic' }}>
                  {report.integrity_certificate.certificate_statement}
                </div>
              </div>
            </section>
          )}

          {/* ── 13. INVESTIGATOR WORKING NOTES & SIGN-OFF ─────────────────────── */}
          {sections.notes && (
            <section className="report-section" style={{ display: 'flex', flexDirection: 'column', gap: 12, borderTop: '2px solid var(--border)', paddingTop: 16 }}>
              <div className="section-title" style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--accent)' }}>13.</span> Investigating Officer Remarks & Attestation
              </div>

              {officerNotes ? (
                <div style={{ padding: 12, background: 'rgba(255,255,255,0.02)', borderRadius: 6, border: '1px solid var(--border)', fontSize: 11.5, color: 'var(--text)', lineHeight: 1.6 }}>
                  <strong>Working Notes:</strong> {officerNotes}
                </div>
              ) : null}

              {/* Signature / Attestation Blocks */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 20,
                marginTop: 20,
                paddingTop: 16,
              }}>
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-bright)' }}>{officerName}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Investigating Officer ({badgeNumber})</div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>{stationUnit}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 8 }}>Signature: __________________________</div>
                </div>

                <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-bright)' }}>Supervisory Review</div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Superintendent of Police / DCP</div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>State Crime Investigation Unit</div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 8 }}>Signature & Seal: ___________________</div>
                </div>

                <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-bright)' }}>Public Prosecutor Office</div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Directorate of Prosecution</div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Court Registry Filing Section</div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 8 }}>Court Seal: [  OFFICIAL FILING  ]</div>
                </div>
              </div>
            </section>
          )}

        </div>
      ) : (
        <div className="glass-panel" style={{ padding: 50, textAlign: 'center', color: 'var(--text-faint)' }}>
          {loading ? 'Compiling 13-section judicial prosecution brief…' : 'Select a case and click "Regenerate" to view the structured report.'}
        </div>
      )}

    </div>
  )
}
