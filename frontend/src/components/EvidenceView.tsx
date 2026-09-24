// Evidence Ledger View — SHA-256 hash chain + Merkle verification dashboard
import React, { useState, useEffect } from 'react'
import { Shield, CheckCircle2, XCircle, Lock, Hash, Search, RefreshCw } from 'lucide-react'

interface VerificationResult {
  case_id: string
  status: string
  total_evidence: number
  valid_chain_items: number
  broken_chain_items: number
  chain_integrity: string
  merkle_root_computed?: string
  merkle_root_expected?: string
  merkle_match?: boolean
  details?: Array<{
    evidence_id: string
    source_table: string
    sequence_index: number
    chain_valid: boolean
    content_sha256: string
    block_hash: string
  }>
}

export default function EvidenceView() {
  const [caseId, setCaseId] = useState('CASE001')
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [caseList, setCaseList] = useState<string[]>([])
  const [batchResults, setBatchResults] = useState<Array<{case_id: string; status: string; total: number}>>([])
  const [batchLoading, setBatchLoading] = useState(false)

  // Load first few cases on mount
  useEffect(() => {
    const ids = Array.from({ length: 10 }, (_, i) => `CASE${String(i + 1).padStart(3, '0')}`)
    setCaseList(ids)
    verifySingle('CASE001')
  }, [])

  const verifySingle = async (id: string) => {
    setLoading(true)
    setCaseId(id)
    try {
      const r = await fetch(`/api/evidence/verify/${id}`)
      const d = await r.json()
      setResult(d)
    } catch {
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const runBatchVerification = async () => {
    setBatchLoading(true)
    const results: Array<{case_id: string; status: string; total: number}> = []
    for (const id of caseList) {
      try {
        const r = await fetch(`/api/evidence/verify/${id}`)
        const d = await r.json()
        results.push({ case_id: id, status: d.chain_integrity || d.status || 'unknown', total: d.total_evidence || 0 })
      } catch {
        results.push({ case_id: id, status: 'error', total: 0 })
      }
    }
    setBatchResults(results)
    setBatchLoading(false)
  }

  const integrityColor = (status: string) => {
    if (status === 'INTACT' || status === 'intact' || status === 'verified') return 'var(--green)'
    if (status === 'PARTIAL') return 'var(--amber)'
    return 'var(--red)'
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <Shield size={18} color="var(--accent)" />
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
          Cryptographic Evidence Ledger
        </h2>
        <span className="badge badge-accent" style={{ fontSize: 10 }}>SHA-256 Hash Chain</span>
        <span className="badge badge-default" style={{ fontSize: 10 }}>Section 65B IEA Compliant</span>
        <div style={{ flex: 1 }} />
        <input
          className="input-field"
          value={caseId}
          onChange={e => setCaseId(e.target.value.toUpperCase())}
          placeholder="CASE001"
          style={{ width: 120, fontFamily: 'var(--mono)' }}
          id="evidence-case-input"
        />
        <button className="btn btn-primary" id="evidence-verify-btn" onClick={() => verifySingle(caseId)} disabled={loading}>
          <Lock size={14} /> {loading ? 'Verifying…' : 'Verify Chain'}
        </button>
        <button className="btn btn-secondary" id="evidence-batch-btn" onClick={runBatchVerification} disabled={batchLoading}>
          <RefreshCw size={14} /> {batchLoading ? 'Running…' : 'Batch (10)'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16 }}>
        {/* Main Verification Result */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {result ? (
            <>
              {/* Status Card */}
              <div className="glass-panel" style={{ padding: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
                  {result.chain_integrity === 'INTACT' ? (
                    <CheckCircle2 size={40} color="var(--green)" />
                  ) : (
                    <XCircle size={40} color="var(--red)" />
                  )}
                  <div>
                    <div style={{ fontSize: 22, fontWeight: 800, color: integrityColor(result.chain_integrity || '') }}>
                      {result.chain_integrity || result.status}
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>
                      {result.case_id} — {result.total_evidence} evidence items verified
                    </div>
                  </div>
                </div>

                {/* Stats */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                  <div className="stat-card" style={{ padding: 12 }}>
                    <div className="stat-label">Valid Chain Links</div>
                    <div className="stat-value" style={{ color: 'var(--green)', fontSize: 24 }}>{result.valid_chain_items}</div>
                  </div>
                  <div className="stat-card" style={{ padding: 12 }}>
                    <div className="stat-label">Broken Links</div>
                    <div className="stat-value" style={{ color: result.broken_chain_items ? 'var(--red)' : 'var(--text-faint)', fontSize: 24 }}>
                      {result.broken_chain_items}
                    </div>
                  </div>
                  <div className="stat-card" style={{ padding: 12 }}>
                    <div className="stat-label">Merkle Match</div>
                    <div className="stat-value" style={{ color: result.merkle_match ? 'var(--green)' : 'var(--amber)', fontSize: 24 }}>
                      {result.merkle_match ? '✓' : '—'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Merkle Root */}
              {result.merkle_root_computed && (
                <div className="glass-panel" style={{ padding: 16 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10 }}>
                    <Hash size={12} style={{ display: 'inline', marginRight: 4 }} /> Merkle Root Verification
                  </div>
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)', marginBottom: 2 }}>Computed Root:</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)', wordBreak: 'break-all', padding: '6px 10px', background: 'rgba(0,210,255,0.06)', borderRadius: 4 }}>
                      {result.merkle_root_computed}
                    </div>
                  </div>
                  {result.merkle_root_expected && (
                    <div>
                      <div style={{ fontSize: 10, color: 'var(--text-faint)', marginBottom: 2 }}>Expected Root (Ground Truth):</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: result.merkle_match ? 'var(--green)' : 'var(--red)', wordBreak: 'break-all', padding: '6px 10px', background: result.merkle_match ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)', borderRadius: 4 }}>
                        {result.merkle_root_expected}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Chain Details Table */}
              {result.details && result.details.length > 0 && (
                <div className="glass-panel" style={{ overflow: 'hidden' }}>
                  <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', fontSize: 12, fontWeight: 600, color: 'var(--text-bright)' }}>
                    Hash Chain Details ({result.details.length} blocks)
                  </div>
                  <div style={{ overflowY: 'auto', maxHeight: 300 }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)' }}>
                          {['#', 'Evidence ID', 'Source', 'SHA-256', 'Status'].map(h => (
                            <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 10, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.details.slice(0, 50).map((d, i) => (
                          <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={{ padding: '8px 12px', fontSize: 11, color: 'var(--text-faint)', fontFamily: 'var(--mono)' }}>{d.sequence_index}</td>
                            <td style={{ padding: '8px 12px', fontSize: 11, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>{d.evidence_id}</td>
                            <td style={{ padding: '8px 12px', fontSize: 11, color: 'var(--text-dim)' }}>{d.source_table}</td>
                            <td style={{ padding: '8px 12px', fontSize: 10, color: 'var(--text-faint)', fontFamily: 'var(--mono)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>{d.content_sha256?.slice(0, 24)}…</td>
                            <td style={{ padding: '8px 12px' }}>
                              {d.chain_valid ? (
                                <CheckCircle2 size={14} color="var(--green)" />
                              ) : (
                                <XCircle size={14} color="var(--red)" />
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="glass-panel" style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)' }}>
              {loading ? 'Verifying cryptographic integrity…' : 'Enter a Case ID and click "Verify Chain" to inspect evidence integrity.'}
            </div>
          )}
        </div>

        {/* Sidebar: Batch Results + Info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Quick Case Buttons */}
          <div className="glass-panel" style={{ padding: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10 }}>Quick Verify</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {caseList.map(id => (
                <button
                  key={id}
                  className={`btn ${caseId === id ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ fontSize: 10, padding: '4px 8px' }}
                  onClick={() => verifySingle(id)}
                >
                  {id}
                </button>
              ))}
            </div>
          </div>

          {/* Batch Results */}
          {batchResults.length > 0 && (
            <div className="glass-panel" style={{ padding: 14, flex: 1, overflowY: 'auto' }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10 }}>
                Batch Verification Results
              </div>
              {batchResults.map((br, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                  {br.status === 'INTACT' || br.status === 'intact' || br.status === 'verified' ? (
                    <CheckCircle2 size={14} color="var(--green)" />
                  ) : (
                    <XCircle size={14} color="var(--red)" />
                  )}
                  <span
                    style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)', cursor: 'pointer' }}
                    onClick={() => verifySingle(br.case_id)}
                  >
                    {br.case_id}
                  </span>
                  <span style={{ flex: 1 }} />
                  <span style={{ fontSize: 10, color: integrityColor(br.status) }}>{br.status}</span>
                  <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>{br.total} items</span>
                </div>
              ))}
            </div>
          )}

          {/* Info Card */}
          <div className="glass-panel" style={{ padding: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 8 }}>About This Module</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}>
              Each evidence record is hashed with SHA-256 and chained via <code style={{ color: 'var(--accent)', fontSize: 11 }}>block_hash = SHA256(previous_hash + content_sha256)</code>. The Merkle root is computed over all leaf block_hash values per case.
            </div>
            <div style={{ fontSize: 11, color: 'var(--amber)', marginTop: 8, lineHeight: 1.5 }}>
              ⚠ This verification does not itself guarantee legal admissibility. It provides cryptographic tamper-evidence for Section 65B certification.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
