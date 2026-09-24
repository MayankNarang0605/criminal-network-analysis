// Network Graph View — vis-network canvas with physics, expand-on-click, right-click menu,
// rich textual relationships inspector, 360° suspect dossier profile, and full Case Intelligence & Assets.
import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { Network as VisNetwork } from 'vis-network'
import { DataSet } from 'vis-data'
import {
  Network,
  MapPin,
  Car,
  Phone,
  CreditCard,
  User,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  ArrowUpRight,
  ArrowDownLeft,
  Shield,
  Layers,
  FileText,
  Activity,
  CheckCircle,
  Clock,
  Sparkles,
  ExternalLink,
  Target,
  DollarSign,
  TrendingUp,
  Radio,
} from 'lucide-react'

interface GraphNode {
  id: string
  label: string
  group: string
  color: string
  alias?: string
  city?: string
}

interface GraphEdge {
  id: string
  from: string
  to: string
  label: string
  confidence?: number
}

interface PersonDossier {
  person_id: string
  full_name: string
  alias?: string
  age?: number
  gender?: string
  city?: string
  occupation?: string
  address?: string
  phone_ids?: string
  vehicle_ids?: string
  organization_ids?: string
  phones?: string[]
  vehicles?: Array<{
    vehicle_id: string
    registration_id: string
    make: string
    model: string
    color: string
    type: string
  }>
  bank_accounts?: Array<{
    account_id: string
    bank_name: string
    branch_city: string
    account_type: string
  }>
  cases_involved?: Array<{
    fir_id: string
    case_id?: string
    role: string
    confidence?: number
    status?: string
  }>
}

interface AssociatedRelationship {
  id: string
  direction: 'outgoing' | 'incoming'
  predicate: string
  partnerId: string
  partnerLabel: string
  partnerGroup: string
  partnerCity?: string
  confidence?: number
}

interface CaseAssetsData {
  case_id: string
  case_title: string
  crime_type: string
  primary_location: string
  total_suspects: number
  firs: Array<{
    fir_id: string
    fir_number: string
    incident_city: string
    incident_date: string
    summary: string
    status: string
  }>
  vehicles_count: number
  vehicles: Array<{
    vehicle_id: string
    registration_id: string
    make: string
    model: string
    color: string
    type: string
    owner_person_id: string
    owner_name: string
    city?: string
  }>
  financial_summary: {
    total_transactions: number
    total_volume: number
    recent_transactions: Array<{
      transaction_id: string
      sender_account: string
      receiver_account: string
      amount: number
      timestamp: string
      type: string
      location: string
    }>
  }
  telecom_summary: {
    total_calls: number
    unique_numbers: number
  }
}

const ENTITY_COLORS: Record<string, string> = {
  Person: '#3b82f6',
  Case: '#8b5cf6',
  Phone: '#10b981',
  Vehicle: '#f59e0b',
  BankAccount: '#06b6d4',
  Location: '#ec4899',
  Organization: '#6366f1',
  Kingpin: '#ef4444',
  Entity: '#64748b',
}

interface CaseItem {
  case_id: string
  case_title: string
  crime_type: string
  difficulty: string
}

export default function NetworkView() {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<VisNetwork | null>(null)
  const nodesRef = useRef<DataSet<any> | null>(null)
  const edgesRef = useRef<DataSet<any> | null>(null)

  const [caseList, setCaseList] = useState<CaseItem[]>([])
  const [selectedCaseId, setSelectedCaseId] = useState('CASE001')
  const [loading, setLoading] = useState(false)
  const [nodeCount, setNodeCount] = useState(0)
  const [edgeCount, setEdgeCount] = useState(0)
  const [source, setSource] = useState('')

  // Selected node state
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const [rawNodes, setRawNodes] = useState<GraphNode[]>([])
  const [rawEdges, setRawEdges] = useState<GraphEdge[]>([])
  const [dossier, setDossier] = useState<PersonDossier | null>(null)
  const [dossierLoading, setDossierLoading] = useState(false)

  // Case-level Assets (Vehicles, Finances, Telecom, FIRs)
  const [caseAssets, setCaseAssets] = useState<CaseAssetsData | null>(null)
  const [caseAssetsLoading, setCaseAssetsLoading] = useState(false)

  // Top Inspector Switcher
  const [panelViewMode, setPanelViewMode] = useState<'entity' | 'case_assets' | 'all'>('entity')

  // Entity-level sub-tabs
  const [entitySubTab, setEntitySubTab] = useState<'all' | 'relationships' | 'dossier' | 'simulation'>('all')
  const [relFilter, setRelFilter] = useState<'all' | 'outgoing' | 'incoming'>('all')

  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; nodeId: string } | null>(null)
  const [disruptResult, setDisruptResult] = useState<any>(null)
  const [disruptLoading, setDisruptLoading] = useState(false)

  // Fetch available cases list on mount
  useEffect(() => {
    fetch('/api/cases?limit=100')
      .then(r => r.json())
      .then(d => {
        const list = Array.isArray(d) ? d : (d.cases || [])
        setCaseList(list)
      })
      .catch(() => {})
  }, [])

  // Fetch Case Assets & Intelligence (Vehicles, Finances, Telecom)
  const loadCaseAssets = useCallback(async (caseId: string) => {
    setCaseAssetsLoading(true)
    try {
      const r = await fetch(`/api/cases/${caseId}/assets`)
      if (r.ok) {
        const data = await r.json()
        setCaseAssets(data)
      } else {
        setCaseAssets(null)
      }
    } catch {
      setCaseAssets(null)
    } finally {
      setCaseAssetsLoading(false)
    }
  }, [])

  // Fetch full 360° suspect dossier when a node is selected
  const selectAndFetchNode = useCallback(async (nodeId: string, directMeta?: GraphNode) => {
    const node = directMeta || nodesRef.current?.get(nodeId)?._meta
    if (node) {
      setSelected(node)
    } else {
      setSelected({ id: nodeId, label: nodeId, group: 'Entity', color: '#64748b' })
    }
    setDisruptResult(null)
    setPanelViewMode('entity')

    if (nodeId.startsWith('P') || node?.group === 'Person' || node?.group === 'Kingpin') {
      setDossierLoading(true)
      try {
        const r = await fetch(`/api/persons/${nodeId}`)
        if (r.ok) {
          const data: PersonDossier = await r.json()
          setDossier(data)
        } else {
          setDossier(null)
        }
      } catch {
        setDossier(null)
      } finally {
        setDossierLoading(false)
      }
    } else {
      setDossier(null)
    }
  }, [])

  const expandNode = useCallback(async (nodeId: string) => {
    try {
      const r = await fetch(`/api/graph/expand/${nodeId}?limit=30`)
      const data = await r.json()
      const newNodes: GraphNode[] = (data.nodes || []).filter((n: GraphNode) => !nodesRef.current?.get(n.id))
      const newEdges: GraphEdge[] = (data.edges || []).filter((e: GraphEdge) => !edgesRef.current?.get(e.id))

      if (nodesRef.current && (newNodes.length > 0 || newEdges.length > 0)) {
        if (newNodes.length > 0) {
          nodesRef.current.add(newNodes.map((n: GraphNode) => ({
            id: n.id,
            label: n.label.length > 16 ? n.label.slice(0, 14) + '…' : n.label,
            title: `${n.label}\n${n.group} | ${n.city || ''}\n${n.alias ? 'Alias: ' + n.alias : ''}`,
            color: {
              background: ENTITY_COLORS[n.group] || '#64748b',
              border: ENTITY_COLORS[n.group] || '#64748b',
              highlight: { background: '#00d2ff', border: '#00d2ff' },
              hover: { background: '#38bdf8', border: '#38bdf8' },
            },
            font: { color: '#f1f5f9', size: 11, face: 'Inter, sans-serif' },
            borderWidth: 1.5,
            size: n.group === 'Kingpin' ? 26 : n.group === 'Case' ? 22 : 18,
            shape: n.group === 'Case' ? 'diamond' : n.group === 'Phone' ? 'dot' : 'ellipse',
            group: n.group,
            _meta: n,
          })))
          setRawNodes(prev => [...prev, ...newNodes])
        }

        if (edgesRef.current && newEdges.length > 0) {
          edgesRef.current.add(newEdges.map((e: GraphEdge) => ({
            id: e.id,
            from: e.from,
            to: e.to,
            label: e.label || '',
            font: { color: '#64748b', size: 9, face: 'Inter' },
            color: { color: 'rgba(100,116,139,0.5)', highlight: 'rgba(0,210,255,0.8)', hover: 'rgba(0,210,255,0.6)' },
            width: 1,
            arrows: { to: { enabled: true, scaleFactor: 0.5 } },
            smooth: { enabled: true, type: 'dynamic', roundness: 0.2 },
          })))
          setRawEdges(prev => [...prev, ...newEdges])
        }

        setNodeCount(nodesRef.current.length)
        if (edgesRef.current) setEdgeCount(edgesRef.current.length)
      }
    } catch (e) {
      console.error('Failed to expand node:', e)
    }
  }, [])

  const loadGraph = useCallback(async (case_id?: string) => {
    setLoading(true)
    setContextMenu(null)
    setDisruptResult(null)
    setSelected(null)
    setDossier(null)

    try {
      const activeCid = case_id || selectedCaseId
      loadCaseAssets(activeCid)

      const url = activeCid ? `/api/graph?case_id=${activeCid}&limit=200` : '/api/graph?limit=200'
      const r = await fetch(url)
      const data = await r.json()
      const nodes: GraphNode[] = data.nodes || []
      const edges: GraphEdge[] = data.edges || []

      setNodeCount(nodes.length)
      setEdgeCount(edges.length)
      setSource(data.source || 'unknown')
      setRawNodes(nodes)
      setRawEdges(edges)

      const visNodes = nodes.map(n => ({
        id: n.id,
        label: n.label.length > 16 ? n.label.slice(0, 14) + '…' : n.label,
        title: `${n.label}\n${n.group} | ${n.city || ''}\n${n.alias ? 'Alias: ' + n.alias : ''}`,
        color: {
          background: ENTITY_COLORS[n.group] || '#64748b',
          border: ENTITY_COLORS[n.group] || '#64748b',
          highlight: { background: '#00d2ff', border: '#00d2ff' },
          hover: { background: '#38bdf8', border: '#38bdf8' },
        },
        font: { color: '#f1f5f9', size: 11, face: 'Inter, sans-serif' },
        borderWidth: 1.5,
        size: n.group === 'Kingpin' ? 26 : n.group === 'Case' ? 22 : 18,
        shape: n.group === 'Case' ? 'diamond' : n.group === 'Phone' ? 'dot' : 'ellipse',
        group: n.group,
        _meta: n,
      }))

      const visEdges = edges.map(e => ({
        id: e.id,
        from: e.from,
        to: e.to,
        label: e.label || '',
        font: { color: '#64748b', size: 9, face: 'Inter' },
        color: { color: 'rgba(100,116,139,0.5)', highlight: 'rgba(0,210,255,0.8)', hover: 'rgba(0,210,255,0.6)' },
        width: 1,
        arrows: { to: { enabled: true, scaleFactor: 0.5 } },
        smooth: { enabled: true, type: 'dynamic', roundness: 0.2 },
      }))

      if (!nodesRef.current) {
        nodesRef.current = new DataSet(visNodes)
        edgesRef.current = new DataSet(visEdges)
      } else {
        nodesRef.current.clear()
        edgesRef.current?.clear()
        nodesRef.current.add(visNodes)
        edgesRef.current?.add(visEdges)
      }

      if (containerRef.current && !networkRef.current) {
        networkRef.current = new VisNetwork(
          containerRef.current,
          { nodes: nodesRef.current, edges: edgesRef.current },
          {
            physics: {
              enabled: true,
              solver: 'forceAtlas2Based',
              forceAtlas2Based: { gravitationalConstant: -50, centralGravity: 0.01, springLength: 120, springConstant: 0.08 },
              stabilization: { iterations: 150 },
            },
            interaction: {
              hover: true,
              tooltipDelay: 200,
              zoomView: true,
              dragNodes: true,
              multiselect: false,
              navigationButtons: false,
            },
            nodes: { borderWidth: 1.5, shadow: false },
            edges: { smooth: { enabled: true, type: 'dynamic', roundness: 0.2 } as any },
            layout: { improvedLayout: false },
          }
        )

        // Single click: select node and load profile + relationships
        networkRef.current.on('click', (params: any) => {
          setContextMenu(null)
          if (params.nodes.length > 0) {
            const nodeId = params.nodes[0]
            selectAndFetchNode(nodeId)
          } else {
            setSelected(null)
            setDossier(null)
          }
        })

        // Double-click: expand 1st degree neighbors
        networkRef.current.on('doubleClick', async (params: any) => {
          if (params.nodes.length > 0) {
            const nodeId = params.nodes[0]
            await expandNode(nodeId)
          }
        })

        // Right-click context menu
        networkRef.current.on('oncontext', (params: any) => {
          params.event.preventDefault()
          if (params.nodes.length > 0) {
            setContextMenu({ x: params.event.clientX, y: params.event.clientY, nodeId: params.nodes[0] })
          }
        })
      } else if (networkRef.current && nodesRef.current && edgesRef.current) {
        networkRef.current.setData({ nodes: nodesRef.current, edges: edgesRef.current })
      }

    } catch (e) {
      console.error('Graph load error:', e)
    } finally {
      setLoading(false)
    }
  }, [expandNode, selectAndFetchNode, selectedCaseId, loadCaseAssets])

  // Center and inspect a connected node
  const handleFocusPartner = (partnerId: string) => {
    if (networkRef.current) {
      networkRef.current.focus(partnerId, {
        scale: 1.3,
        animation: { duration: 500, easingFunction: 'easeInOutQuad' },
      })
      networkRef.current.selectNodes([partnerId])
    }
    selectAndFetchNode(partnerId)
  }

  const simulateDisrupt = async (nodeId: string) => {
    setDisruptLoading(true)
    setContextMenu(null)
    try {
      const r = await fetch('/api/graph/disrupt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ node_id: nodeId }),
      })
      const data = await r.json()
      setDisruptResult(data)
      setEntitySubTab('simulation')
    } catch (e) {
      console.error('Disrupt error:', e)
    } finally {
      setDisruptLoading(false)
    }
  }

  useEffect(() => {
    loadGraph(selectedCaseId)
    return () => {
      if (networkRef.current) {
        try { networkRef.current.destroy() } catch {}
        networkRef.current = null
      }
      nodesRef.current = null
      edgesRef.current = null
    }
  }, [selectedCaseId, loadGraph])

  const handlePrevCase = () => {
    const idx = caseList.findIndex(c => c.case_id === selectedCaseId)
    if (idx > 0) {
      setSelectedCaseId(caseList[idx - 1].case_id)
    }
  }

  const handleNextCase = () => {
    const idx = caseList.findIndex(c => c.case_id === selectedCaseId)
    if (idx >= 0 && idx < caseList.length - 1) {
      setSelectedCaseId(caseList[idx + 1].case_id)
    }
  }

  // Calculate direct textual relationships for the selected node
  const associatedRelationships = useMemo<AssociatedRelationship[]>(() => {
    if (!selected) return []
    const nodeMap = new Map<string, GraphNode>()
    rawNodes.forEach(n => nodeMap.set(n.id, n))

    const rels: AssociatedRelationship[] = []

    rawEdges.forEach(e => {
      if (e.from === selected.id) {
        const partner = nodeMap.get(e.to)
        rels.push({
          id: e.id,
          direction: 'outgoing',
          predicate: e.label || 'CONNECTED_TO',
          partnerId: e.to,
          partnerLabel: partner ? partner.label : e.to,
          partnerGroup: partner ? partner.group : 'Entity',
          partnerCity: partner?.city,
          confidence: e.confidence,
        })
      } else if (e.to === selected.id) {
        const partner = nodeMap.get(e.from)
        rels.push({
          id: e.id,
          direction: 'incoming',
          predicate: e.label || 'CONNECTED_TO',
          partnerId: e.from,
          partnerLabel: partner ? partner.label : e.from,
          partnerGroup: partner ? partner.group : 'Entity',
          partnerCity: partner?.city,
          confidence: e.confidence,
        })
      }
    })

    return rels
  }, [selected, rawNodes, rawEdges])

  // Filter relationships by direction
  const filteredRelationships = useMemo(() => {
    if (relFilter === 'all') return associatedRelationships
    return associatedRelationships.filter(r => r.direction === relFilter)
  }, [associatedRelationships, relFilter])

  const currentCaseMeta = caseList.find(c => c.case_id === selectedCaseId)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: 'calc(100vh - 100px)' }}>
      {/* Controls / Case Selector Topbar */}
      <div className="glass-panel" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Network size={16} color="var(--accent)" />
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)' }}>Case Network Graph:</span>
        </div>

        {/* Case Dropdown Selector */}
        <select
          className="input-field"
          value={selectedCaseId}
          onChange={e => setSelectedCaseId(e.target.value)}
          style={{ width: 340, fontWeight: 600, fontSize: 13, background: 'rgba(255,255,255,0.06)' }}
          id="graph-case-select"
        >
          {caseList.length === 0 ? (
            <option value="CASE001">CASE001 (Loading cases…)</option>
          ) : (
            caseList.map(c => (
              <option key={c.case_id} value={c.case_id}>
                {c.case_id} — {c.case_title.length > 32 ? c.case_title.slice(0, 30) + '…' : c.case_title} ({c.difficulty})
              </option>
            ))
          )}
        </select>

        {/* Prev / Next Case Navigation */}
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            className="btn btn-secondary"
            onClick={handlePrevCase}
            disabled={caseList.findIndex(c => c.case_id === selectedCaseId) <= 0}
            title="Previous Case"
            style={{ padding: '6px 10px', fontSize: 12 }}
            id="graph-prev-case-btn"
          >
            ‹ Prev
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleNextCase}
            disabled={caseList.findIndex(c => c.case_id === selectedCaseId) >= caseList.length - 1}
            title="Next Case"
            style={{ padding: '6px 10px', fontSize: 12 }}
            id="graph-next-case-btn"
          >
            Next ›
          </button>
        </div>

        {/* Active Stats */}
        <span className="badge badge-accent" style={{ fontSize: 11, fontWeight: 600 }}>
          {selectedCaseId} Subgraph
        </span>
        <span className="badge badge-default">{nodeCount} nodes</span>
        <span className="badge badge-default">{edgeCount} edges</span>

        {caseAssets && (
          <>
            <span className="badge badge-default" style={{ fontSize: 11, color: '#f59e0b', display: 'flex', alignItems: 'center', gap: 3 }}>
              <Car size={11} color="#f59e0b" /> {caseAssets.vehicles_count} Vehicles
            </span>
            <span className="badge badge-default" style={{ fontSize: 11, color: '#06b6d4', display: 'flex', alignItems: 'center', gap: 3 }}>
              <DollarSign size={11} color="#06b6d4" /> ₹{caseAssets.financial_summary.total_volume.toLocaleString()} ({caseAssets.financial_summary.total_transactions} txs)
            </span>
          </>
        )}

        <div style={{ flex: 1 }} />

        <button
          className="btn btn-secondary"
          onClick={() => loadGraph(selectedCaseId)}
          id="graph-refresh-btn"
          disabled={loading}
          style={{ fontSize: 12 }}
        >
          {loading ? 'Rendering…' : '↻ Re-center'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 12, flex: 1, minHeight: 0 }}>
        {/* Graph Canvas Frame */}
        <div
          id="network-canvas-frame"
          style={{
            flex: 1,
            background: 'var(--graph-bg)',
            borderRadius: 12,
            border: '1px solid var(--border)',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {/* Isolated canvas mount point without React children */}
          <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

          {loading && (
            <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', color: 'var(--accent)', fontFamily: 'var(--mono)', fontSize: 13, pointerEvents: 'none' }}>
              Loading case graph…
            </div>
          )}
          <div style={{ position: 'absolute', bottom: 12, left: 12, fontSize: 11, color: 'var(--text-faint)', pointerEvents: 'none' }}>
            Click node to view textual relationships & dossier • Double-click to expand • Right-click for options
          </div>
        </div>

        {/* Right Inspector Panel */}
        <div
          id="network-inspector-panel"
          style={{
            width: 410,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            overflowY: 'auto',
            maxHeight: '100%',
            paddingRight: 4,
          }}
        >
          {/* Primary View Switcher: Node Inspector vs Case Assets & Finances */}
          <div style={{ display: 'flex', background: 'rgba(255,255,255,0.03)', padding: 3, borderRadius: 8, gap: 2, border: '1px solid var(--border)', flexShrink: 0 }}>
            <button
              onClick={() => setPanelViewMode('entity')}
              className={`btn ${panelViewMode === 'entity' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ flex: 1, padding: '6px 8px', fontSize: 11, borderRadius: 6 }}
            >
              {selected ? `Node: ${selected.label.slice(0, 10)}…` : 'Select Node'}
            </button>
            <button
              onClick={() => setPanelViewMode('case_assets')}
              className={`btn ${panelViewMode === 'case_assets' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ flex: 1, padding: '6px 8px', fontSize: 11, borderRadius: 6 }}
            >
              Case Intelligence
            </button>
            <button
              onClick={() => setPanelViewMode('all')}
              className={`btn ${panelViewMode === 'all' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ flex: 1, padding: '6px 8px', fontSize: 11, borderRadius: 6 }}
            >
              All Details
            </button>
          </div>

          {/* ==================== 1. SELECTED NODE INSPECTOR ==================== */}
          {(panelViewMode === 'entity' || panelViewMode === 'all') && (
            <>
              {!selected && panelViewMode === 'entity' ? (
                <div className="glass-panel" style={{ padding: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <Target size={16} color="var(--accent)" />
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-bright)' }}>Investigation Inspector</span>
                  </div>
                  <p style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.5, margin: '0 0 12px 0' }}>
                    Click on any node in the canvas to inspect its complete profile:
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text)' }}>
                      <Network size={14} color="#38bdf8" />
                      <span><strong>Textual Relationships:</strong> Outgoing & incoming connections with partner names & confidence.</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text)' }}>
                      <MapPin size={14} color="#ec4899" />
                      <span><strong>Location & Address:</strong> Registered residence and city records.</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text)' }}>
                      <Car size={14} color="#f59e0b" />
                      <span><strong>Registered Vehicles:</strong> Vehicle plate, make, model & owner.</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text)' }}>
                      <CreditCard size={14} color="#06b6d4" />
                      <span><strong>Finances:</strong> Bank accounts & transaction linkages.</span>
                    </div>
                  </div>
                  <div style={{ marginTop: 14 }}>
                    <button
                      className="btn btn-secondary"
                      style={{ width: '100%', fontSize: 12 }}
                      onClick={() => setPanelViewMode('case_assets')}
                    >
                      View Case Vehicles & Finances ➔
                    </button>
                  </div>
                </div>
              ) : selected ? (
                <>
                  {/* Selected Entity Header Card */}
                  <div className="glass-panel" style={{ padding: 14, borderLeft: `4px solid ${ENTITY_COLORS[selected.group] || 'var(--accent)'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                      <div>
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Selected Entity
                        </span>
                        <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-bright)', margin: '2px 0' }}>
                          {selected.label}
                        </h3>
                      </div>
                      <span
                        className="badge"
                        style={{
                          background: ENTITY_COLORS[selected.group] ? `${ENTITY_COLORS[selected.group]}22` : 'rgba(255,255,255,0.1)',
                          color: ENTITY_COLORS[selected.group] || 'var(--text-bright)',
                          border: `1px solid ${ENTITY_COLORS[selected.group]}55`,
                          fontSize: 11,
                          fontWeight: 700,
                        }}
                      >
                        {selected.group}
                      </span>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10, alignItems: 'center' }}>
                      <span className="badge badge-default" style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
                        {selected.id}
                      </span>
                      {(selected.city || dossier?.city) && (
                        <span className="badge badge-default" style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}>
                          <MapPin size={10} color="#ec4899" />
                          {dossier?.city || selected.city}
                        </span>
                      )}
                      {selected.alias && (
                        <span className="badge badge-default" style={{ fontSize: 11 }}>
                          Alias: {selected.alias}
                        </span>
                      )}
                      {dossier?.occupation && (
                        <span className="badge badge-default" style={{ fontSize: 11 }}>
                          {dossier.occupation}
                        </span>
                      )}
                    </div>

                    {/* Quick Action Buttons */}
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        className="btn btn-primary"
                        style={{ flex: 1, fontSize: 11, padding: '6px 8px' }}
                        onClick={() => expandNode(selected.id)}
                        id="expand-node-btn"
                        title="Expand 1st-degree connections into current canvas"
                      >
                        + Expand
                      </button>
                      <button
                        className="btn btn-secondary"
                        style={{ flex: 1, fontSize: 11, padding: '6px 8px' }}
                        onClick={() => handleFocusPartner(selected.id)}
                        title="Center and highlight this entity"
                      >
                        Focus
                      </button>
                      <button
                        className="btn btn-secondary"
                        style={{ flex: 1, fontSize: 11, padding: '6px 8px' }}
                        onClick={() => simulateDisrupt(selected.id)}
                        disabled={disruptLoading}
                        id="disrupt-node-btn"
                        title="Simulate network severance impact"
                      >
                        {disruptLoading ? '…' : '⚡ Disrupt'}
                      </button>
                    </div>
                  </div>

                  {/* Sub-Tabs for Selected Entity */}
                  <div style={{ display: 'flex', background: 'rgba(255,255,255,0.03)', padding: 3, borderRadius: 8, gap: 2, border: '1px solid var(--border)' }}>
                    <button
                      onClick={() => setEntitySubTab('all')}
                      className={`btn ${entitySubTab === 'all' ? 'btn-primary' : 'btn-ghost'}`}
                      style={{ flex: 1, padding: '4px 6px', fontSize: 10, borderRadius: 6 }}
                    >
                      All Info
                    </button>
                    <button
                      onClick={() => setEntitySubTab('relationships')}
                      className={`btn ${entitySubTab === 'relationships' ? 'btn-primary' : 'btn-ghost'}`}
                      style={{ flex: 1, padding: '4px 6px', fontSize: 10, borderRadius: 6 }}
                    >
                      Links ({associatedRelationships.length})
                    </button>
                    <button
                      onClick={() => setEntitySubTab('dossier')}
                      className={`btn ${entitySubTab === 'dossier' ? 'btn-primary' : 'btn-ghost'}`}
                      style={{ flex: 1, padding: '4px 6px', fontSize: 10, borderRadius: 6 }}
                    >
                      Dossier
                    </button>
                    {disruptResult && (
                      <button
                        onClick={() => setEntitySubTab('simulation')}
                        className={`btn ${entitySubTab === 'simulation' ? 'btn-primary' : 'btn-ghost'}`}
                        style={{ flex: 1, padding: '4px 6px', fontSize: 10, borderRadius: 6 }}
                      >
                        ⚡ Risk
                      </button>
                    )}
                  </div>

                  {/* 1.1 ASSOCIATED RELATIONSHIPS (TEXTUAL FORMAT) */}
                  {(entitySubTab === 'all' || entitySubTab === 'relationships') && (
                    <div className="glass-panel" style={{ padding: 14 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Network size={14} color="var(--accent)" />
                          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            Associated Relationships
                          </span>
                        </div>
                        <span className="badge badge-default" style={{ fontSize: 10 }}>
                          {associatedRelationships.length} {associatedRelationships.length === 1 ? 'connection' : 'connections'}
                        </span>
                      </div>

                      {/* Filter chips if multiple relationships */}
                      {associatedRelationships.length > 2 && (
                        <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
                          {(['all', 'outgoing', 'incoming'] as const).map(filter => (
                            <button
                              key={filter}
                              onClick={() => setRelFilter(filter)}
                              style={{
                                padding: '3px 8px',
                                fontSize: 10,
                                borderRadius: 4,
                                border: '1px solid',
                                borderColor: relFilter === filter ? 'var(--accent)' : 'var(--border)',
                                background: relFilter === filter ? 'rgba(0, 210, 255, 0.15)' : 'transparent',
                                color: relFilter === filter ? 'var(--accent)' : 'var(--text-faint)',
                                cursor: 'pointer',
                                textTransform: 'capitalize',
                              }}
                            >
                              {filter === 'all' ? `All (${associatedRelationships.length})` : filter === 'outgoing' ? `➔ Outgoing (${associatedRelationships.filter(r => r.direction === 'outgoing').length})` : `⬅ Incoming (${associatedRelationships.filter(r => r.direction === 'incoming').length})`}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* List of Relationships in Textual Format */}
                      {filteredRelationships.length === 0 ? (
                        <div style={{ fontSize: 12, color: 'var(--text-faint)', padding: '12px 6px', textAlign: 'center', background: 'rgba(255,255,255,0.02)', borderRadius: 6 }}>
                          {associatedRelationships.length === 0
                            ? 'No direct relationships found in this case subgraph. Click "+ Expand" above to search 1st-degree contacts.'
                            : 'No relationships match the selected filter.'}
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 300, overflowY: 'auto' }}>
                          {filteredRelationships.map((rel, idx) => (
                            <div
                              key={`${rel.id}-${idx}`}
                              style={{
                                background: 'rgba(255,255,255,0.03)',
                                border: '1px solid var(--border)',
                                borderRadius: 8,
                                padding: 10,
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 6,
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                  {rel.direction === 'outgoing' ? (
                                    <span
                                      className="badge"
                                      style={{
                                        background: 'rgba(56, 189, 248, 0.15)',
                                        color: '#38bdf8',
                                        border: '1px solid rgba(56, 189, 248, 0.3)',
                                        fontSize: 10,
                                        padding: '2px 6px',
                                      }}
                                    >
                                      ➔ Outgoing
                                    </span>
                                  ) : (
                                    <span
                                      className="badge"
                                      style={{
                                        background: 'rgba(16, 185, 129, 0.15)',
                                        color: '#10b981',
                                        border: '1px solid rgba(16, 185, 129, 0.3)',
                                        fontSize: 10,
                                        padding: '2px 6px',
                                      }}
                                    >
                                      ⬅ Incoming
                                    </span>
                                  )}
                                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.04em' }}>
                                    {rel.predicate}
                                  </span>
                                </div>

                                {rel.confidence !== undefined && (
                                  <span
                                    style={{
                                      fontSize: 10,
                                      fontFamily: 'var(--mono)',
                                      color: rel.confidence >= 0.7 ? '#10b981' : rel.confidence >= 0.5 ? '#f59e0b' : 'var(--text-faint)',
                                    }}
                                  >
                                    {Math.round(rel.confidence * 100)}% conf
                                  </span>
                                )}
                              </div>

                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 }}>
                                <div>
                                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-bright)' }}>
                                    {rel.partnerLabel}
                                  </div>
                                  <div style={{ fontSize: 11, color: 'var(--text-faint)', fontFamily: 'var(--mono)' }}>
                                    {rel.partnerId} {rel.partnerCity ? `• ${rel.partnerCity}` : ''}
                                  </div>
                                </div>

                                <button
                                  className="btn btn-secondary"
                                  onClick={() => handleFocusPartner(rel.partnerId)}
                                  style={{ padding: '4px 8px', fontSize: 10 }}
                                  title="Focus node in graph"
                                >
                                  Inspect ➔
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 1.2 SUSPECT DOSSIER (LOCATION, VEHICLES, PHONES, ACCOUNTS) */}
                  {(entitySubTab === 'all' || entitySubTab === 'dossier') && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {/* Location & Address */}
                      <div className="glass-panel" style={{ padding: 14 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                          <MapPin size={14} color="#ec4899" />
                          <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            Location & Registered Address
                          </span>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                            <span style={{ color: 'var(--text-faint)' }}>City / District:</span>
                            <span style={{ fontWeight: 600, color: 'var(--text-bright)' }}>
                              {dossier?.city || selected.city || 'Unknown'}
                            </span>
                          </div>
                          <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 4 }}>
                            Address on Police File:
                          </div>
                          <div
                            style={{
                              fontSize: 12,
                              color: dossier?.address ? 'var(--text)' : 'var(--text-faint)',
                              background: 'rgba(255,255,255,0.02)',
                              padding: '8px 10px',
                              borderRadius: 6,
                              border: '1px solid var(--border)',
                              fontStyle: dossier?.address ? 'normal' : 'italic',
                            }}
                          >
                            {dossier?.address || (dossierLoading ? 'Fetching address records…' : 'No residential address on file.')}
                          </div>
                        </div>
                      </div>

                      {/* Suspect Registered Vehicles */}
                      <div className="glass-panel" style={{ padding: 14 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Car size={14} color="#f59e0b" />
                            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              Registered Vehicles
                            </span>
                          </div>
                          <span className="badge badge-default" style={{ fontSize: 10 }}>
                            {dossier?.vehicles?.length || 0}
                          </span>
                        </div>

                        {dossierLoading ? (
                          <div style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>Loading RTO vehicle records…</div>
                        ) : dossier?.vehicles && dossier.vehicles.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {dossier.vehicles.map((v, i) => (
                              <div
                                key={`${v.vehicle_id}-${i}`}
                                style={{
                                  background: 'rgba(255,255,255,0.02)',
                                  border: '1px solid var(--border)',
                                  borderRadius: 6,
                                  padding: '8px 10px',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                }}
                              >
                                <div>
                                  <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)', color: '#f59e0b' }}>
                                    {v.registration_id}
                                  </div>
                                  <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
                                    {v.make} {v.model} ({v.color})
                                  </div>
                                </div>
                                <span className="badge badge-default" style={{ fontSize: 10 }}>
                                  {v.type}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic', padding: '4px 0' }}>
                            No registered motor vehicles linked directly to this person.
                          </div>
                        )}
                      </div>

                      {/* Suspect Registered Phones */}
                      <div className="glass-panel" style={{ padding: 14 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Phone size={14} color="#10b981" />
                            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              Phones & SIM Cards
                            </span>
                          </div>
                          <span className="badge badge-default" style={{ fontSize: 10 }}>
                            {dossier?.phones?.length || 0}
                          </span>
                        </div>

                        {dossier?.phones && dossier.phones.length > 0 ? (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                            {dossier.phones.map((phone, i) => (
                              <div
                                key={`${phone}-${i}`}
                                style={{
                                  background: 'rgba(16, 185, 129, 0.08)',
                                  border: '1px solid rgba(16, 185, 129, 0.25)',
                                  borderRadius: 6,
                                  padding: '5px 8px',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 5,
                                  fontSize: 11,
                                  fontFamily: 'var(--mono)',
                                  color: 'var(--text-bright)',
                                }}
                              >
                                <Phone size={10} color="#10b981" />
                                <span>+91 {phone}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>
                            No registered mobile numbers found.
                          </div>
                        )}
                      </div>

                      {/* Linked Financial Accounts */}
                      <div className="glass-panel" style={{ padding: 14 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <CreditCard size={14} color="#06b6d4" />
                            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              Financial Accounts
                            </span>
                          </div>
                          <span className="badge badge-default" style={{ fontSize: 10 }}>
                            {dossier?.bank_accounts?.length || 0}
                          </span>
                        </div>

                        {dossier?.bank_accounts && dossier.bank_accounts.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {dossier.bank_accounts.map((acc, i) => (
                              <div
                                key={`${acc.account_id}-${i}`}
                                style={{
                                  background: 'rgba(255,255,255,0.02)',
                                  border: '1px solid var(--border)',
                                  borderRadius: 6,
                                  padding: '8px 10px',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)', color: '#06b6d4' }}>
                                    {acc.account_id}
                                  </span>
                                  <span className="badge badge-default" style={{ fontSize: 10 }}>
                                    {acc.account_type || 'Savings'}
                                  </span>
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                                  {acc.bank_name} {acc.branch_city ? `• ${acc.branch_city}` : ''}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>
                            No linked bank accounts flagged.
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 1.3 DISRUPTION SIMULATION */}
                  {(entitySubTab === 'all' || entitySubTab === 'simulation') && disruptResult && (
                    <div className="glass-panel" style={{ padding: 14, borderLeft: '4px solid var(--amber)' }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--amber)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
                        ⚠ SIMULATION ONLY
                      </div>
                      <div style={{ marginBottom: 8 }}>
                        <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--red)' }}>
                          {disruptResult.impact_score}<span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-faint)' }}>/100</span>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>Network Impact Score</div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {[
                          ['Component Δ', `+${disruptResult.graph_after?.component_delta}`],
                          ['Reachability ↓', `${disruptResult.graph_after?.reachability_reduction_pct}%`],
                          ['Financial Disruption', `${disruptResult.financial_disruption_pct}%`],
                          ['Comm Disruption', `${disruptResult.communication_disruption_pct}%`],
                          ['Severed Relationships', disruptResult.severed_relationships],
                        ].map(([label, val]) => (
                          <div key={String(label)} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                            <span style={{ color: 'var(--text-faint)' }}>{label}</span>
                            <span style={{ color: 'var(--text)', fontFamily: 'var(--mono)' }}>{val}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </>
          )}

          {/* ==================== 2. CASE-LEVEL INTELLIGENCE & ASSETS ==================== */}
          {(panelViewMode === 'case_assets' || panelViewMode === 'all') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Case Assets Header */}
              <div className="glass-panel" style={{ padding: 14, borderLeft: '4px solid var(--accent)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Case Intelligence & Assets
                    </span>
                    <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-bright)', margin: '2px 0' }}>
                      {caseAssets?.case_title || selectedCaseId}
                    </h3>
                  </div>
                  <span className="badge badge-accent" style={{ fontSize: 10 }}>
                    {caseAssets?.crime_type || currentCaseMeta?.crime_type}
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginTop: 10 }}>
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px 8px', borderRadius: 6, border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Vehicles</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#f59e0b' }}>{caseAssets?.vehicles_count || 0}</div>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px 8px', borderRadius: 6, border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Finances</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#06b6d4' }}>
                      ₹{caseAssets ? (caseAssets.financial_summary.total_volume / 100000).toFixed(1) + 'L' : '0'}
                    </div>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: '6px 8px', borderRadius: 6, border: '1px solid var(--border)' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-faint)' }}>Telecom CDR</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#10b981' }}>{caseAssets?.telecom_summary.total_calls || 0}</div>
                  </div>
                </div>
              </div>

              {/* Case Registered Vehicles List */}
              <div className="glass-panel" style={{ padding: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Car size={14} color="#f59e0b" />
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Case Registered Vehicles ({caseAssets?.vehicles_count || 0})
                    </span>
                  </div>
                </div>

                {caseAssetsLoading ? (
                  <div style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>Loading vehicles for this case…</div>
                ) : caseAssets && caseAssets.vehicles.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 260, overflowY: 'auto' }}>
                    {caseAssets.vehicles.map((v, idx) => (
                      <div
                        key={`${v.vehicle_id}-${idx}`}
                        style={{
                          background: 'rgba(255,255,255,0.02)',
                          border: '1px solid var(--border)',
                          borderRadius: 6,
                          padding: '8px 10px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)', color: '#f59e0b' }}>
                              {v.registration_id}
                            </span>
                            <span className="badge badge-default" style={{ fontSize: 9 }}>
                              {v.type}
                            </span>
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>
                            {v.make} {v.model} ({v.color})
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 2 }}>
                            Owner: <strong style={{ color: 'var(--text)' }}>{v.owner_name}</strong> ({v.owner_person_id})
                          </div>
                        </div>

                        <button
                          className="btn btn-secondary"
                          onClick={() => handleFocusPartner(v.owner_person_id)}
                          style={{ padding: '3px 8px', fontSize: 10 }}
                          title="Focus suspect owner in graph"
                        >
                          Focus Owner ➔
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>
                    No vehicles registered for suspects in this case.
                  </div>
                )}
              </div>

              {/* Case Financial Flow & Transactions */}
              <div className="glass-panel" style={{ padding: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <DollarSign size={14} color="#06b6d4" />
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Case Financial Flow ({caseAssets?.financial_summary.total_transactions || 0} Txs)
                    </span>
                  </div>
                  {caseAssets && (
                    <span className="badge badge-accent" style={{ fontSize: 10 }}>
                      ₹{caseAssets.financial_summary.total_volume.toLocaleString()}
                    </span>
                  )}
                </div>

                {caseAssets && caseAssets.financial_summary.recent_transactions.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 240, overflowY: 'auto' }}>
                    {caseAssets.financial_summary.recent_transactions.map((tx, idx) => (
                      <div
                        key={`${tx.transaction_id}-${idx}`}
                        style={{
                          background: 'rgba(255,255,255,0.02)',
                          border: '1px solid var(--border)',
                          borderRadius: 6,
                          padding: '7px 10px',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-faint)' }}>
                            {tx.sender_account} ➔ {tx.receiver_account}
                          </span>
                          <span style={{ fontSize: 12, fontWeight: 700, color: '#06b6d4', fontFamily: 'var(--mono)' }}>
                            ₹{tx.amount.toLocaleString()}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-faint)', marginTop: 2 }}>
                          <span>{tx.type} • {tx.location}</span>
                          <span>{tx.timestamp.split('T')[0]}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>
                    No recorded financial transfers in this case.
                  </div>
                )}
              </div>

              {/* Case Official FIR Narrative */}
              {caseAssets?.firs && caseAssets.firs.length > 0 && (
                <div className="glass-panel" style={{ padding: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <FileText size={14} color="#8b5cf6" />
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-bright)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      FIR Record: {caseAssets.firs[0].fir_number}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.5 }}>
                    {caseAssets.firs[0].summary}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Entity Legend */}
          <div className="glass-panel" style={{ padding: 14, flexShrink: 0 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
              Entity Legend
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '4px 8px' }}>
              {Object.entries(ENTITY_COLORS).map(([type, color]) => (
                <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
                  <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{type}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Context Menu on Right Click */}
      {contextMenu && (
        <div
          style={{
            position: 'fixed',
            top: contextMenu.y,
            left: contextMenu.x,
            zIndex: 1000,
            background: 'var(--surface)',
            border: '1px solid var(--border-strong)',
            borderRadius: 8,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            minWidth: 180,
          }}
          onMouseLeave={() => setContextMenu(null)}
        >
          {[
            ['Inspect & Load Dossier', () => { selectAndFetchNode(contextMenu.nodeId); setContextMenu(null) }],
            ['Expand Neighbors', () => { expandNode(contextMenu.nodeId); setContextMenu(null) }],
            ['Simulate Disruption', () => simulateDisrupt(contextMenu.nodeId)],
            ['Center in Canvas', () => { networkRef.current?.focus(contextMenu.nodeId, { scale: 1.5, animation: true }); setContextMenu(null) }],
          ].map(([label, action]) => (
            <button
              key={String(label)}
              onClick={() => (action as Function)()}
              style={{
                width: '100%',
                padding: '10px 16px',
                textAlign: 'left',
                background: 'none',
                border: 'none',
                color: 'var(--text)',
                fontSize: 13,
                cursor: 'pointer',
                display: 'block',
              }}
              className="context-menu-item"
            >
              {String(label)}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
