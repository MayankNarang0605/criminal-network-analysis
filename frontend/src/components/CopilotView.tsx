// AI Copilot View — interactive chat terminal querying POST /api/copilot/query
import React, { useState, useRef, useEffect } from 'react'
import { MessageSquare, Send, Loader2, Bot, User, Link2, AlertTriangle } from 'lucide-react'

interface Citation {
  source_type: string
  identifier: string
  summary: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  engine?: string
  citations?: Citation[]
  leads?: string[]
  timestamp: string
}

export default function CopilotView() {
  const [messages, setMessages] = useState<Message[]>([{
    role: 'assistant',
    content: 'Welcome to CrimeNet AI Copilot. I can help you investigate cases, analyze networks, and identify patterns. All my responses are strictly grounded in evidence — every claim cites a case_id, transaction_id, or CDR record.\n\nTry asking:\n• "What are the key suspects in CASE001?"\n• "Show financial anomalies"\n• "Who are the top kingpin candidates?"\n• "Summarize cross-case overlaps"',
    engine: 'system',
    citations: [],
    leads: [],
    timestamp: new Date().toISOString(),
  }])
  const [input, setInput] = useState('')
  const [caseContext, setCaseContext] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const sendQuery = async () => {
    if (!input.trim() || loading) return
    const userMsg: Message = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const r = await fetch('/api/copilot/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: input,
          case_id: caseContext || undefined,
          context_mode: 'comprehensive',
        }),
      })
      const data = await r.json()
      const assistantMsg: Message = {
        role: 'assistant',
        content: data.answer || data.detail || 'No response generated.',
        engine: data.engine_used || 'unknown',
        citations: data.citations || [],
        leads: data.recommended_leads || [],
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Connection error. Please ensure the backend is running on port 8000.',
        engine: 'error',
        citations: [],
        leads: [],
        timestamp: new Date().toISOString(),
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 100px)', gap: 12 }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <Bot size={18} color="var(--accent)" />
        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)' }}>Investigative AI Copilot</span>
        <span className="badge badge-accent" style={{ fontSize: 10 }}>Evidence-Grounded</span>
        <span className="badge badge-default" style={{ fontSize: 10 }}>Deterministic Fallback Active</span>
        <div style={{ flex: 1 }} />
        <input
          className="input-field"
          placeholder="Case context (e.g. CASE001)"
          value={caseContext}
          onChange={e => setCaseContext(e.target.value)}
          style={{ width: 160 }}
          id="copilot-case-ctx"
        />
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="glass-panel"
        style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 14 }}
        id="copilot-messages"
      >
        {messages.map((msg, i) => (
          <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row' }}>
            {/* Avatar */}
            <div style={{
              width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
              background: msg.role === 'user' ? 'rgba(99,102,241,0.15)' : 'rgba(0,210,255,0.1)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {msg.role === 'user' ? <User size={16} color="#6366f1" /> : <Bot size={16} color="var(--accent)" />}
            </div>

            {/* Content */}
            <div style={{
              maxWidth: '75%',
              background: msg.role === 'user' ? 'rgba(99,102,241,0.08)' : 'rgba(0,210,255,0.04)',
              border: `1px solid ${msg.role === 'user' ? 'rgba(99,102,241,0.2)' : 'var(--border)'}`,
              borderRadius: 12,
              padding: '12px 16px',
            }}>
              {/* Engine badge */}
              {msg.engine && msg.engine !== 'system' && msg.engine !== 'error' && (
                <div style={{ marginBottom: 8, display: 'flex', gap: 6 }}>
                  <span className="badge badge-default" style={{ fontSize: 9 }}>{msg.engine}</span>
                </div>
              )}

              {/* Message text */}
              <div style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                {msg.content}
              </div>

              {/* Citations */}
              {msg.citations && msg.citations.length > 0 && (
                <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Link2 size={10} /> Evidence Citations
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {msg.citations.map((c, j) => (
                      <div key={j} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
                        <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)', fontSize: 10, padding: '1px 6px', borderRadius: 3, background: 'rgba(0,210,255,0.08)' }}>
                          {c.source_type}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)' }}>{c.identifier}</span>
                        <span style={{ color: 'var(--text-faint)', flex: 1 }}>{c.summary.slice(0, 60)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended Leads */}
              {msg.leads && msg.leads.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Recommended Leads</div>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {msg.leads.map((lead, j) => (
                      <span key={j} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(245,158,11,0.1)', color: 'var(--amber)', border: '1px solid rgba(245,158,11,0.2)' }}>
                        {lead}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Timestamp */}
              <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 6, textAlign: 'right' }}>
                {new Date(msg.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-faint)', fontSize: 13 }}>
            <Loader2 size={14} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
            Analyzing evidence and generating grounded response…
          </div>
        )}
      </div>

      {/* Input */}
      <div className="glass-panel" style={{ padding: '10px 16px', display: 'flex', gap: 10, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 8px', color: 'var(--text-faint)', fontSize: 11 }}>
          <AlertTriangle size={12} /> All responses cite real evidence
        </div>
        <input
          id="copilot-input"
          className="input-field"
          style={{ flex: 1 }}
          placeholder="Ask about cases, suspects, financial patterns, or network connections..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendQuery()}
          disabled={loading}
        />
        <button
          id="copilot-send-btn"
          className="btn btn-primary"
          onClick={sendQuery}
          disabled={loading || !input.trim()}
        >
          <Send size={14} />
          {loading ? 'Analyzing…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
