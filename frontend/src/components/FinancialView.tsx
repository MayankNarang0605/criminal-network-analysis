// Financial Intelligence View — Transaction Analysis, Multi-Hop Money Flows, Laundering Patterns & Cross-Case Links
import React, { useState, useEffect, useMemo } from 'react'
import {
  CreditCard, DollarSign, ArrowRight, ArrowDownRight, ArrowUpRight,
  AlertTriangle, ShieldAlert, RefreshCw, Filter, Search, Layers,
  Activity, Repeat, GitMerge, GitBranch, Users, Eye, Check, Copy,
  ExternalLink, Network, FileText, ChevronRight, CornerDownRight,
  Building, Calendar, Clock, ArrowUp, ArrowDown, Sparkles
} from 'lucide-react'
import { NavView } from './Sidebar'

interface TransactionItem {
  transaction_id: string
  case_id: string
  timestamp: string
  date_formatted: string
  amount: number
  amount_formatted: string
  sender_account: string
  sender_name: string
  sender_bank: string
  receiver_account: string
  receiver_name: string
  receiver_bank: string
  location: string
  is_unusual: boolean
  unusual_reason?: string | null
  transaction_type: string
  description: string
}

interface FlowStep {
  hop: number
  from_account: string
  from_name: string
  from_bank: string
  to_account: string
  to_name: string
  to_bank: string
  amount: number
  amount_formatted: string
  timestamp: string
  date: string
  tx_id: string
  latency_hours?: number
}

interface MoneyFlowChain {
  chain_id: string
  hop_count: number
  origin_account: string
  origin_name: string
  intermediary_account: string
  intermediary_name: string
  destination_account: string
  destination_name: string
  initial_amount: number
  initial_amount_formatted: string
  forwarded_amount: number
  forwarded_amount_formatted: string
  retention_percentage: number
  total_latency_hours: number
  classification: string
  steps: FlowStep[]
  evidence_ids: string[]
}

interface PatternAlert {
  pattern_id: string
  pattern_type: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  title: string
  entity: string
  account_id: string
  event_count: number
  total_amount: number
  formatted_amount: string
  explanation: string
  evidence: string[]
  first_date: string
  last_date: string
}

interface CrossCaseAccount {
  account_id: string
  entity_name: string
  bank_name: string
  branch_city: string
  case_count: number
  linked_cases: string[]
  total_cross_volume: number
  formatted_volume: string
  total_transactions: number
  evidence_ids: string[]
  relationship: string
}

interface CrossCasePerson {
  person_id: string
  name: string
  alias: string
  city: string
  case_count: number
  linked_cases: string[]
  sender_accounts_count: number
  total_received: number
  formatted_received: string
  evidence_ids: string[]
}

interface AccountSummaryItem {
  account_id: string
  entity_name: string
  bank_name: string
  branch_city: string
  total_inflow: number
  formatted_inflow: string
  total_outflow: number
  formatted_outflow: string
  inflow_count: number
  outflow_count: number
  net_flow: number
  formatted_net: string
  is_flagged: boolean
}

interface FinancialData {
  case_id?: string | null
  summary: {
    total_money_analyzed: number
    formatted_total_money: string
    total_transactions: number
    suspicious_transactions_count: number
    suspicious_volume: number
    formatted_suspicious_volume: string
    suspicious_accounts_count: number
    active_patterns_count: number
    money_flow_chains_count: number
    cross_case_accounts_count: number
    pattern_counts: {
      structuring: number
      fan_in: number
      fan_out: number
      mule_funnel: number
      circular_flow: number
    }
  }
  transactions: TransactionItem[]
  money_flow_chains: MoneyFlowChain[]
  patterns: PatternAlert[]
  cross_case: {
    accounts: CrossCaseAccount[]
    persons: CrossCasePerson[]
  }
  top_accounts: AccountSummaryItem[]
}

interface CaseOption {
  case_id: string
  title?: string
  crime_type?: string
}

interface FinancialViewProps {
  onNavigate?: (v: NavView) => void
}

const SEV_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  CRITICAL: { bg: 'rgba(239, 68, 68, 0.12)', text: '#ef4444', border: 'rgba(239, 68, 68, 0.3)' },
  HIGH: { bg: 'rgba(245, 158, 11, 0.12)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.3)' },
  MEDIUM: { bg: 'rgba(0, 210, 255, 0.12)', text: '#00d2ff', border: 'rgba(0, 210, 255, 0.3)' },
  LOW: { bg: 'rgba(16, 185, 129, 0.12)', text: '#10b981', border: 'rgba(16, 185, 129, 0.3)' },
}

export default function FinancialView({ onNavigate }: FinancialViewProps) {
  const [data, setData] = useState<FinancialData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Scope & Navigation
  const [caseList, setCaseList] = useState<CaseOption[]>([])
  const [selectedCase, setSelectedCase] = useState<string>('CASE001')
  const [activeTab, setActiveTab] = useState<'transactions' | 'flows' | 'patterns' | 'crosscase' | 'accounts'>('transactions')

  // Sub-Filters
  const [txFilterUnusualOnly, setTxFilterUnusualOnly] = useState<boolean>(false)
  const [txSearchQuery, setTxSearchQuery] = useState<string>('')
  const [patternTypeFilter, setPatternTypeFilter] = useState<string>('ALL')
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Load cases
  useEffect(() => {
    fetch('/api/cases?limit=100')
      .then(r => r.json())
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

  // Load financial data
  const loadFinancialData = async () => {
    setLoading(true)
    setError(null)
    try {
      const url = selectedCase && selectedCase !== 'ALL'
        ? `/api/analytics/financial?case_id=${selectedCase}`
        : '/api/analytics/financial'
      const res = await fetch(url)
      if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`)
      const json: FinancialData = await res.json()
      setData(json)
    } catch (err: any) {
      setError(err.message || 'Failed to fetch financial forensics')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadFinancialData()
  }, [selectedCase])

  // Filtered transactions
  const displayedTransactions = useMemo(() => {
    if (!data?.transactions) return []
    let list = data.transactions
    if (txFilterUnusualOnly) {
      list = list.filter(t => t.is_unusual)
    }
    if (txSearchQuery.trim()) {
      const q = txSearchQuery.toLowerCase()
      list = list.filter(t =>
        t.sender_account.toLowerCase().includes(q) ||
        t.receiver_account.toLowerCase().includes(q) ||
        t.sender_name.toLowerCase().includes(q) ||
        t.receiver_name.toLowerCase().includes(q) ||
        t.transaction_id.toLowerCase().includes(q) ||
        t.location.toLowerCase().includes(q)
      )
    }
    return list
  }, [data?.transactions, txFilterUnusualOnly, txSearchQuery])

  // Filtered patterns
  const displayedPatterns = useMemo(() => {
    if (!data?.patterns) return []
    if (patternTypeFilter === 'ALL') return data.patterns
    return data.patterns.filter(p => p.pattern_type.toLowerCase().includes(patternTypeFilter.toLowerCase()))
  }, [data?.patterns, patternTypeFilter])

  const copyEvidence = (id: string) => {
    navigator.clipboard.writeText(id)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1800)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* ── 1. Top Header: The Central Question ─────────────────────────── */}
      <div className="glass-panel" style={{ padding: '20px 24px', background: 'linear-gradient(135deg, rgba(15,23,42,0.9) 0%, rgba(30,41,59,0.9) 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <CreditCard size={22} color="var(--accent)" />
              <h2 style={{ fontSize: 18, fontWeight: 800, margin: 0, color: 'var(--text-bright)', letterSpacing: '0.03em' }}>
                Financial Forensics & Money Laundering Network
              </h2>
              <span className="badge" style={{ background: 'rgba(16,185,129,0.15)', color: '#10b981', border: '1px solid rgba(16,185,129,0.3)', fontWeight: 700 }}>
                FATF Forensic Typologies
              </span>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}>
              “How is money moving through the criminal network, and are there suspicious financial patterns?”
            </p>
          </div>

          {/* Scope Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)' }}>Scope:</span>
            <select
              id="fin-case-dropdown"
              value={selectedCase}
              onChange={e => setSelectedCase(e.target.value)}
              className="input-field"
              style={{ minWidth: 220, fontWeight: 600, background: 'rgba(15,23,42,0.95)' }}
            >
              <option value="ALL">🌐 All Cases (Syndicate-Wide)</option>
              <optgroup label="Specific Cases">
                {caseList.map(c => (
                  <option key={c.case_id} value={c.case_id}>
                    {c.case_id} {c.title ? `— ${c.title}` : ''}
                  </option>
                ))}
              </optgroup>
            </select>

            <button
              id="fin-refresh-btn"
              className="btn btn-secondary"
              onClick={loadFinancialData}
              disabled={loading}
              title="Refresh Financial Analysis"
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>

        {/* ── 2. KPI Risk Ribbon (Requirement 5: Financial Risk/Alerts) ─── */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
          gap: 12,
          marginTop: 18,
          paddingTop: 16,
          borderTop: '1px solid rgba(255,255,255,0.08)',
        }}>
          {/* Total Money Analyzed */}
          <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--text-faint)', fontWeight: 700, letterSpacing: '0.04em' }}>
              Total Money Analyzed
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-bright)', marginTop: 4, fontFamily: 'var(--mono)' }}>
              {loading ? '…' : data?.summary.formatted_total_money ?? '₹0'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {data?.summary.total_transactions ?? 0} transactions
            </div>
          </div>

          {/* Suspicious Volume */}
          <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
            <div style={{ fontSize: 11, textTransform: 'uppercase', color: '#ef4444', fontWeight: 700, letterSpacing: '0.04em' }}>
              Suspicious Volume
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#ef4444', marginTop: 4, fontFamily: 'var(--mono)' }}>
              {loading ? '…' : data?.summary.formatted_suspicious_volume ?? '₹0'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {data?.summary.suspicious_transactions_count ?? 0} suspicious transfers
            </div>
          </div>

          {/* Suspicious Accounts */}
          <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }}>
            <div style={{ fontSize: 11, textTransform: 'uppercase', color: '#f59e0b', fontWeight: 700, letterSpacing: '0.04em' }}>
              Suspicious Accounts
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#f59e0b', marginTop: 4, fontFamily: 'var(--mono)' }}>
              {loading ? '…' : data?.summary.suspicious_accounts_count ?? 0}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              Funnels / mules / smurfing
            </div>
          </div>

          {/* Detected Laundering Patterns */}
          <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(0,210,255,0.08)', border: '1px solid rgba(0,210,255,0.2)' }}>
            <div style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--accent)', fontWeight: 700, letterSpacing: '0.04em' }}>
              Detected Patterns
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--accent)', marginTop: 4, fontFamily: 'var(--mono)' }}>
              {loading ? '…' : data?.summary.active_patterns_count ?? 0}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              5 FATF typologies active
            </div>
          </div>

          {/* Money Flow Chains */}
          <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(129,140,248,0.08)', border: '1px solid rgba(129,140,248,0.2)' }}>
            <div style={{ fontSize: 11, textTransform: 'uppercase', color: '#818cf8', fontWeight: 700, letterSpacing: '0.04em' }}>
              Money Flow Chains
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#818cf8', marginTop: 4, fontFamily: 'var(--mono)' }}>
              {loading ? '…' : data?.summary.money_flow_chains_count ?? 0}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              Multi-hop transfer paths
            </div>
          </div>
        </div>
      </div>

      {/* ── 3. Primary Workspace Navigation Tabs ─────────────────────────── */}
      <div style={{ display: 'flex', gap: 6, background: 'rgba(15,23,42,0.7)', padding: 4, borderRadius: 8, border: '1px solid var(--border)', overflowX: 'auto' }}>
        {[
          { id: 'transactions', label: `💰 1. Transaction Analysis (${data?.transactions.length ?? 0})` },
          { id: 'flows', label: `🔄 2. Money Flow Visualizer (${data?.money_flow_chains.length ?? 0})` },
          { id: 'patterns', label: `🚨 3. Laundering Typologies (${data?.patterns.length ?? 0})` },
          { id: 'crosscase', label: `🔗 4. Cross-Case Connections (${data?.cross_case.accounts.length ?? 0})` },
          { id: 'accounts', label: `📊 5. Account Risk Ledger (${data?.top_accounts.length ?? 0})` },
        ].map(t => (
          <button
            key={t.id}
            id={`tab-fin-${t.id}`}
            className={`btn ${activeTab === t.id ? 'btn-primary' : 'btn-ghost'}`}
            style={{ padding: '8px 16px', fontSize: 13, fontWeight: 700, whiteSpace: 'nowrap' }}
            onClick={() => setActiveTab(t.id as any)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── 4. Main Workspace Display ────────────────────────────────────── */}

      {/* ── TAB 1: TRANSACTION ANALYSIS ─────────────────────────────────── */}
      {activeTab === 'transactions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Controls Bar */}
          <div className="glass-panel" style={{ padding: '12px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button
                id="btn-filter-all-tx"
                className={`btn ${!txFilterUnusualOnly ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '5px 12px', fontSize: 12, fontWeight: 600 }}
                onClick={() => setTxFilterUnusualOnly(false)}
              >
                All Transactions ({data?.transactions.length ?? 0})
              </button>

              <button
                id="btn-filter-unusual-tx"
                className={`btn ${txFilterUnusualOnly ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '5px 12px', fontSize: 12, fontWeight: 600, color: txFilterUnusualOnly ? '#fff' : '#ef4444' }}
                onClick={() => setTxFilterUnusualOnly(true)}
              >
                🚨 Unusual Only ({data?.summary.suspicious_transactions_count ?? 0})
              </button>
            </div>

            <div style={{ position: 'relative', minWidth: 260 }}>
              <Search size={14} color="var(--text-faint)" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }} />
              <input
                id="tx-search-input"
                type="text"
                className="input-field"
                placeholder="Search sender, receiver, account, TX ID..."
                value={txSearchQuery}
                onChange={e => setTxSearchQuery(e.target.value)}
                style={{ paddingLeft: 32, fontSize: 12, width: '100%' }}
              />
            </div>
          </div>

          {/* Transactions Ledger Table */}
          <div className="glass-panel" style={{ overflow: 'hidden', padding: 0 }}>
            <div style={{
              padding: '12px 20px',
              background: 'rgba(15,23,42,0.6)',
              borderBottom: '1px solid var(--border)',
              display: 'grid',
              gridTemplateColumns: '130px 220px 40px 220px 140px 1fr 120px',
              fontSize: 11,
              fontWeight: 700,
              textTransform: 'uppercase',
              color: 'var(--text-faint)',
              letterSpacing: '0.04em',
            }}>
              <div>Timestamp</div>
              <div>Sender (Outflow)</div>
              <div style={{ textAlign: 'center' }}>→</div>
              <div>Receiver (Inflow)</div>
              <div style={{ textAlign: 'right' }}>Amount (INR)</div>
              <div>Forensic Observation</div>
              <div style={{ textAlign: 'right' }}>Evidence</div>
            </div>

            <div style={{ maxHeight: 600, overflowY: 'auto' }}>
              {loading ? (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Analyzing transaction ledger…</div>
              ) : displayedTransactions.length === 0 ? (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>No transactions match criteria.</div>
              ) : (
                displayedTransactions.map((tx, idx) => (
                  <div
                    key={tx.transaction_id || idx}
                    id={`tx-row-${idx}`}
                    style={{
                      padding: '12px 20px',
                      borderBottom: '1px solid var(--border)',
                      display: 'grid',
                      gridTemplateColumns: '130px 220px 40px 220px 140px 1fr 120px',
                      alignItems: 'center',
                      background: tx.is_unusual ? 'rgba(239, 68, 68, 0.04)' : 'transparent',
                      borderLeft: tx.is_unusual ? '3px solid #ef4444' : '3px solid transparent',
                    }}
                  >
                    {/* Date */}
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-bright)' }}>{tx.date_formatted}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-faint)', fontFamily: 'var(--mono)' }}>{tx.location}</div>
                    </div>

                    {/* Sender */}
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>{tx.sender_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                        {tx.sender_account} • {tx.sender_bank}
                      </div>
                    </div>

                    {/* Arrow */}
                    <div style={{ textAlign: 'center' }}>
                      <ArrowRight size={14} color={tx.is_unusual ? '#ef4444' : 'var(--text-faint)'} />
                    </div>

                    {/* Receiver */}
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>{tx.receiver_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                        {tx.receiver_account} • {tx.receiver_bank}
                      </div>
                    </div>

                    {/* Amount */}
                    <div style={{ textAlign: 'right' }}>
                      <div style={{
                        fontSize: 14,
                        fontWeight: 800,
                        fontFamily: 'var(--mono)',
                        color: tx.is_unusual ? '#ef4444' : 'var(--accent)',
                      }}>
                        {tx.amount_formatted}
                      </div>
                    </div>

                    {/* Observation / Unusual Reason */}
                    <div style={{ paddingLeft: 16 }}>
                      {tx.is_unusual ? (
                        <span style={{
                          padding: '3px 8px',
                          borderRadius: 4,
                          background: 'rgba(239,68,68,0.12)',
                          color: '#ef4444',
                          border: '1px solid rgba(239,68,68,0.3)',
                          fontSize: 11,
                          fontWeight: 600,
                        }}>
                          🚨 {tx.unusual_reason || 'Unusual Outlier'}
                        </span>
                      ) : (
                        <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>Routine Transfer</span>
                      )}
                    </div>

                    {/* Evidence ID chip */}
                    <div style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => copyEvidence(tx.transaction_id)}
                        title="Copy Evidence ID"
                        style={{
                          padding: '2px 8px',
                          borderRadius: 4,
                          background: 'rgba(0,210,255,0.08)',
                          border: '1px solid rgba(0,210,255,0.2)',
                          color: 'var(--accent)',
                          fontFamily: 'var(--mono)',
                          fontSize: 11,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        {copiedId === tx.transaction_id ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
                        {tx.transaction_id}
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 2: MONEY FLOW VISUALIZER (Account A -> Account B -> Account C) */}
      {activeTab === 'flows' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="glass-panel" style={{ padding: '14px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
                Multi-Hop Money Flow Pathways ({data?.money_flow_chains.length ?? 0} Chains Tracked)
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0' }}>
                Visualizes sequential layering transfers: Account A → Account B → Account C with latency and passthrough ratio.
              </p>
            </div>
            <span className="badge badge-accent">Interactive Flow Pathways</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {loading ? (
              <div className="glass-panel" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Tracing money flow pathways…</div>
            ) : data?.money_flow_chains.length === 0 ? (
              <div className="glass-panel" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                No multi-hop relay chains detected for this scope.
              </div>
            ) : (
              data?.money_flow_chains.map((chain, cIdx) => (
                <div
                  key={chain.chain_id || cIdx}
                  id={`flow-card-${cIdx}`}
                  className="glass-panel"
                  style={{
                    padding: 0,
                    overflow: 'hidden',
                    borderLeft: '4px solid #818cf8',
                  }}
                >
                  {/* Flow Header */}
                  <div style={{
                    padding: '12px 20px',
                    background: 'rgba(15,23,42,0.6)',
                    borderBottom: '1px solid var(--border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 12,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <GitMerge size={16} color="#818cf8" />
                      <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-bright)' }}>
                        {chain.origin_name} → {chain.destination_name}
                      </span>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: 4,
                        background: 'rgba(99,102,241,0.15)',
                        color: '#818cf8',
                        fontSize: 11,
                        fontFamily: 'var(--mono)',
                        fontWeight: 600,
                      }}>
                        {chain.hop_count}-Hop Chain
                      </span>
                      <span className="badge" style={{ background: 'rgba(239,68,68,0.12)', color: '#ef4444', fontSize: 11 }}>
                        {chain.classification}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: 12 }}>
                      <span style={{ color: 'var(--text-muted)' }}>
                        Initial: <strong style={{ color: 'var(--accent)', fontFamily: 'var(--mono)' }}>{chain.initial_amount_formatted}</strong>
                      </span>
                      <span style={{ color: 'var(--text-muted)' }}>
                        Forwarded: <strong style={{ color: '#ef4444', fontFamily: 'var(--mono)' }}>{chain.forwarded_amount_formatted}</strong>
                      </span>
                      <span style={{ color: 'var(--text-muted)' }}>
                        Passthrough: <strong style={{ color: '#f59e0b', fontFamily: 'var(--mono)' }}>{chain.retention_percentage}%</strong>
                      </span>
                    </div>
                  </div>

                  {/* Flow Steps Visualization */}
                  <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${chain.steps.length}, 1fr)`, gap: 14 }}>
                      {chain.steps.map((step, sIdx) => (
                        <div
                          key={sIdx}
                          style={{
                            padding: '12px 14px',
                            borderRadius: 8,
                            background: 'rgba(0,0,0,0.3)',
                            border: '1px solid rgba(255,255,255,0.06)',
                            position: 'relative',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                            <span style={{ fontSize: 11, fontWeight: 700, color: '#818cf8', fontFamily: 'var(--mono)' }}>
                              HOP {step.hop}
                            </span>
                            {step.latency_hours !== undefined && (
                              <span style={{ fontSize: 10, color: '#f59e0b', fontFamily: 'var(--mono)' }}>
                                +{step.latency_hours}h relay
                              </span>
                            )}
                          </div>

                          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                            {step.from_name}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                            {step.from_account}
                          </div>

                          <div style={{ margin: '8px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <ArrowRight size={14} color="var(--accent)" />
                            <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                              {step.amount_formatted}
                            </span>
                          </div>

                          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                            {step.to_name}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                            {step.to_account}
                          </div>

                          <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: 10, color: 'var(--text-faint)' }}>{step.date}</span>
                            <button
                              onClick={() => copyEvidence(step.tx_id)}
                              style={{
                                padding: '1px 6px',
                                borderRadius: 4,
                                background: 'rgba(0,210,255,0.08)',
                                border: '1px solid rgba(0,210,255,0.15)',
                                color: 'var(--accent)',
                                fontSize: 10,
                                fontFamily: 'var(--mono)',
                                cursor: 'pointer',
                              }}
                            >
                              {copiedId === step.tx_id ? '✓' : step.tx_id}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ── TAB 3: MONEY LAUNDERING PATTERNS ────────────────────────────── */}
      {activeTab === 'patterns' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Typology Sub-Filters */}
          <div className="glass-panel" style={{ padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-faint)', marginRight: 4 }}>Typology:</span>
            {[
              { id: 'ALL', label: `All Patterns (${data?.patterns.length ?? 0})` },
              { id: 'Structuring', label: `📦 Structuring / Smurfing (${data?.summary.pattern_counts.structuring ?? 0})` },
              { id: 'Fan-in', label: `📥 Fan-in Aggregation (${data?.summary.pattern_counts.fan_in ?? 0})` },
              { id: 'Fan-out', label: `📤 Fan-out Dispersal (${data?.summary.pattern_counts.fan_out ?? 0})` },
              { id: 'Mule', label: `🔀 Mule Funnel (${data?.summary.pattern_counts.mule_funnel ?? 0})` },
              { id: 'Circular', label: `🔄 Circular Flow (${data?.summary.pattern_counts.circular_flow ?? 0})` },
            ].map(p => (
              <button
                key={p.id}
                id={`filter-pat-${p.id.toLowerCase()}`}
                className={`btn ${patternTypeFilter === p.id ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '5px 12px', fontSize: 12, fontWeight: 600 }}
                onClick={() => setPatternTypeFilter(p.id)}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Pattern Cards Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 14 }}>
            {loading ? (
              <div className="glass-panel" style={{ gridColumn: '1 / -1', padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Scanning for money laundering patterns…</div>
            ) : displayedPatterns.length === 0 ? (
              <div className="glass-panel" style={{ gridColumn: '1 / -1', padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                No patterns match current typology filter.
              </div>
            ) : (
              displayedPatterns.map((pat, pIdx) => {
                const sevStyle = SEV_COLORS[pat.severity] || SEV_COLORS.HIGH
                return (
                  <div
                    key={pat.pattern_id || pIdx}
                    id={`pattern-card-${pIdx}`}
                    className="glass-panel"
                    style={{
                      padding: '18px 20px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      gap: 12,
                      borderLeft: `4px solid ${sevStyle.text}`,
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                        <span style={{
                          padding: '3px 8px',
                          borderRadius: 4,
                          background: sevStyle.bg,
                          color: sevStyle.text,
                          border: `1px solid ${sevStyle.border}`,
                          fontSize: 11,
                          fontWeight: 700,
                        }}>
                          {pat.pattern_type.toUpperCase()}
                        </span>

                        <span style={{ fontSize: 14, fontWeight: 800, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                          {pat.formatted_amount}
                        </span>
                      </div>

                      <h3 style={{ fontSize: 15, fontWeight: 700, margin: '4px 0 2px', color: 'var(--text-bright)' }}>
                        {pat.title}
                      </h3>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                        Account: {pat.account_id} • {pat.event_count} related events
                      </div>

                      <p style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.5, margin: '10px 0' }}>
                        {pat.explanation}
                      </p>
                    </div>

                    {/* Evidence Chips */}
                    <div>
                      <div style={{ fontSize: 10, textTransform: 'uppercase', color: 'var(--text-faint)', fontWeight: 700, marginBottom: 4 }}>
                        Evidence Citations ({pat.evidence.length})
                      </div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {pat.evidence.map(evId => (
                          <button
                            key={evId}
                            onClick={() => copyEvidence(evId)}
                            title="Click to copy evidence ID"
                            style={{
                              padding: '2px 8px',
                              borderRadius: 4,
                              background: 'rgba(0,210,255,0.08)',
                              border: '1px solid rgba(0,210,255,0.2)',
                              color: 'var(--accent)',
                              fontFamily: 'var(--mono)',
                              fontSize: 11,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            {copiedId === evId ? <Check size={11} color="#10b981" /> : <Copy size={11} />}
                            {evId}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}

      {/* ── TAB 4: CROSS-CASE CONNECTIONS ───────────────────────────────── */}
      {activeTab === 'crosscase' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Header Banner */}
          <div className="glass-panel" style={{ padding: '16px 20px' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
              Cross-Jurisdiction Financial Nexus
            </h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>
              Identifies bank accounts and individuals operating as financial bridges across independent criminal case files.
            </p>
          </div>

          {/* Cross-case Accounts Table */}
          <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{
              padding: '12px 20px',
              background: 'rgba(15,23,42,0.6)',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                Bank Accounts Present in Multiple Cases ({data?.cross_case.accounts.length ?? 0})
              </span>
            </div>

            <div style={{ maxHeight: 420, overflowY: 'auto' }}>
              {data?.cross_case.accounts.map((acc, idx) => (
                <div
                  key={acc.account_id || idx}
                  style={{
                    padding: '12px 20px',
                    borderBottom: '1px solid var(--border)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 12,
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)' }}>
                        {acc.entity_name}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--accent)', fontFamily: 'var(--mono)', fontWeight: 600 }}>
                        {acc.account_id}
                      </span>
                      <span className="badge badge-danger">
                        {acc.case_count} Cases Linked
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      {acc.bank_name} • {acc.branch_city} • {acc.total_transactions} total transactions
                    </div>

                    <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                      {acc.linked_cases.map(cid => (
                        <span key={cid} style={{
                          padding: '1px 6px',
                          borderRadius: 4,
                          background: cid === selectedCase ? 'rgba(0,210,255,0.2)' : 'rgba(99,102,241,0.15)',
                          color: cid === selectedCase ? 'var(--accent)' : '#818cf8',
                          fontSize: 10,
                          fontFamily: 'var(--mono)',
                          fontWeight: 600,
                        }}>
                          {cid}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 15, fontWeight: 800, color: '#ef4444', fontFamily: 'var(--mono)' }}>
                      {acc.formatted_volume}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>Cross-case volume</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Cross-case Persons */}
          {data?.cross_case.persons && data.cross_case.persons.length > 0 && (
            <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{
                padding: '12px 20px',
                background: 'rgba(15,23,42,0.6)',
                borderBottom: '1px solid var(--border)',
              }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>
                  Persons Receiving Money From Multiple Suspicious Entities ({data.cross_case.persons.length})
                </span>
              </div>

              <div style={{ maxHeight: 350, overflowY: 'auto' }}>
                {data.cross_case.persons.map((p, idx) => (
                  <div
                    key={p.person_id || idx}
                    style={{
                      padding: '12px 20px',
                      borderBottom: '1px solid var(--border)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)' }}>{p.name}</span>
                        {p.alias && p.alias !== 'None' && (
                          <span style={{ fontSize: 11, color: '#f59e0b' }}>"{p.alias}"</span>
                        )}
                        <span className="badge badge-accent">{p.case_count} Cases</span>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                        {p.city} • Received transfers from {p.sender_accounts_count} distinct sender accounts
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                        {p.formatted_received}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>Cumulative Received</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 5: FORENSIC ACCOUNT RISK LEDGER ──────────────────────────── */}
      {activeTab === 'accounts' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="glass-panel" style={{ padding: '14px 20px' }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
              Forensic Account Risk Ledger
            </h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0' }}>
              Aggregated inflows, outflows, and net liquidity across primary target accounts in scope.
            </p>
          </div>

          <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{
              padding: '12px 20px',
              background: 'rgba(15,23,42,0.6)',
              borderBottom: '1px solid var(--border)',
              display: 'grid',
              gridTemplateColumns: '180px 180px 140px 140px 140px 120px',
              fontSize: 11,
              fontWeight: 700,
              textTransform: 'uppercase',
              color: 'var(--text-faint)',
            }}>
              <div>Account & Bank</div>
              <div>Account Holder</div>
              <div style={{ textAlign: 'right' }}>Total Inflow</div>
              <div style={{ textAlign: 'right' }}>Total Outflow</div>
              <div style={{ textAlign: 'right' }}>Net Flow</div>
              <div style={{ textAlign: 'center' }}>Risk Status</div>
            </div>

            <div style={{ maxHeight: 500, overflowY: 'auto' }}>
              {data?.top_accounts.map((acc, idx) => (
                <div
                  key={acc.account_id || idx}
                  style={{
                    padding: '12px 20px',
                    borderBottom: '1px solid var(--border)',
                    display: 'grid',
                    gridTemplateColumns: '180px 180px 140px 140px 140px 120px',
                    alignItems: 'center',
                    background: acc.is_flagged ? 'rgba(239,68,68,0.04)' : 'transparent',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)', fontFamily: 'var(--mono)' }}>
                      {acc.account_id}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{acc.bank_name}</div>
                  </div>

                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)' }}>{acc.entity_name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{acc.branch_city}</div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#10b981', fontFamily: 'var(--mono)' }}>
                      {acc.formatted_inflow}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>{acc.inflow_count} txns</div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#ef4444', fontFamily: 'var(--mono)' }}>
                      {acc.formatted_outflow}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>{acc.outflow_count} txns</div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: acc.net_flow >= 0 ? '#10b981' : '#ef4444', fontFamily: 'var(--mono)' }}>
                      {acc.formatted_net}
                    </div>
                  </div>

                  <div style={{ textAlign: 'center' }}>
                    {acc.is_flagged ? (
                      <span className="badge badge-danger">🚨 FLAGGED</span>
                    ) : (
                      <span className="badge badge-info">ROUTINE</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
