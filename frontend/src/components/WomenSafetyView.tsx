// Women Safety Intelligence View — corridors, hotspots, case flags
import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { ShieldAlert, MapPin, AlertTriangle, Users, TrendingUp } from 'lucide-react'

interface Corridor {
  location_id: string
  area: string
  city: string
  incident_count: number
  risk_score: number
}

export default function WomenSafetyView() {
  const [corridors, setCorridors] = useState<Corridor[]>([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({ total: 0, highRisk: 0, maxScore: 0 })

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch('/api/geo/corridors')
        const d = await r.json()
        const corrs: Corridor[] = d.corridors || []
        setCorridors(corrs)
        const highRisk = corrs.filter(c => (c.risk_score || 0) >= 5).length
        const maxScore = Math.max(...corrs.map(c => c.risk_score || 0), 0)
        setStats({ total: corrs.length, highRisk, maxScore })
      } catch {}
      setLoading(false)
    }
    load()
  }, [])

  const riskColor = (score: number) => score >= 7 ? '#ef4444' : score >= 5 ? '#f59e0b' : score >= 3 ? '#06b6d4' : '#10b981'

  const chartData = corridors.slice(0, 12).map(c => ({
    name: c.area.slice(0, 12),
    risk_score: c.risk_score || 0,
    incidents: c.incident_count || 0,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <ShieldAlert size={18} color="var(--red)" />
        <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, color: 'var(--text-bright)' }}>
          Women Safety Intelligence Module
        </h2>
        <span className="badge badge-default" style={{ background: 'rgba(239,68,68,0.15)', color: 'var(--red)', fontSize: 10 }}>Human Review Only</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: 'var(--text-faint)' }}>No autonomous action</span>
      </div>

      {/* Disclaimer */}
      <div style={{ padding: '10px 16px', background: 'rgba(245,158,11,0.06)', borderRadius: 8, border: '1px solid rgba(245,158,11,0.15)' }}>
        <div style={{ fontSize: 12, color: 'var(--amber)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={14} />
          This module provides analytical intelligence for human review only. No autonomous surveillance, tracking, or operational action is implied or recommended. All findings require investigator verification.
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <div className="stat-card">
          <div className="stat-label">Surveillance Corridors</div>
          <div className="stat-value">{stats.total}</div>
          <div className="stat-footer" style={{ color: 'var(--red)' }}>
            <MapPin size={12} style={{ display: 'inline', marginRight: 4 }} /> Identified zones
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">High-Risk Corridors</div>
          <div className="stat-value" style={{ color: 'var(--red)' }}>{stats.highRisk}</div>
          <div className="stat-footer" style={{ color: 'var(--amber)' }}>
            <AlertTriangle size={12} style={{ display: 'inline', marginRight: 4 }} /> Risk score ≥ 5
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Peak Risk Score</div>
          <div className="stat-value" style={{ color: 'var(--red)' }}>{stats.maxScore.toFixed(1)}</div>
          <div className="stat-footer" style={{ color: 'var(--text-faint)' }}>
            <TrendingUp size={12} style={{ display: 'inline', marginRight: 4 }} /> Maximum observed
          </div>
        </div>
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="glass-panel" style={{ padding: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)', marginBottom: 12 }}>
            Corridor Risk Scores
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData} barSize={24}>
              <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#141d33', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, color: '#f1f5f9', fontSize: 12 }} />
              <Bar dataKey="risk_score" name="Risk Score" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={index} fill={riskColor(entry.risk_score)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Corridors Table */}
      <div className="glass-panel" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <MapPin size={14} color="var(--red)" />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)' }}>Identified Surveillance Corridors</span>
        </div>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-faint)' }}>Analyzing corridors…</div>
        ) : corridors.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-faint)' }}>No corridor data available.</div>
        ) : (
          <div style={{ overflowY: 'auto', maxHeight: 400 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Location ID', 'Area', 'City', 'Incidents', 'Risk Score', 'Risk Level'].map(h => (
                    <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontSize: 10, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {corridors.map((c, i) => {
                  const risk = c.risk_score || 0
                  const level = risk >= 7 ? 'CRITICAL' : risk >= 5 ? 'HIGH' : risk >= 3 ? 'MEDIUM' : 'LOW'
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }} className="table-row-hover">
                      <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{c.location_id}</td>
                      <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text)' }}>{c.area}</td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text-dim)' }}>{c.city}</td>
                      <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text)', fontFamily: 'var(--mono)', textAlign: 'center' }}>{c.incident_count}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 60, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                            <div style={{ height: '100%', borderRadius: 2, background: riskColor(risk), width: `${Math.min(100, risk * 10)}%` }} />
                          </div>
                          <span style={{ fontSize: 13, fontFamily: 'var(--mono)', color: riskColor(risk), fontWeight: 700 }}>{risk.toFixed(1)}</span>
                        </div>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: riskColor(risk) + '22', color: riskColor(risk) }}>
                          {level}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
