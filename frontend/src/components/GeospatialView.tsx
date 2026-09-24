// Geospatial View — Leaflet map with location pins, CCTV/ANPR tracks, corridors
import React, { useEffect, useRef, useState } from 'react'
import { MapPin, Eye, AlertTriangle, Shield } from 'lucide-react'

interface Location {
  location_id: string
  city: string
  area: string
  location_name: string
  latitude: number
  longitude: number
  location_type: string
}

interface Movement {
  event_id: string
  camera_id: string
  location_id: string
  timestamp: string
  detection_type: string
  plate_number: string
  description: string
  latitude?: number
  longitude?: number
}

interface Corridor {
  location_id: string
  area: string
  city: string
  incident_count: number
  risk_score: number
}

let L: any = null

export default function GeospatialView() {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<any>(null)
  const [locations, setLocations] = useState<Location[]>([])
  const [movements, setMovements] = useState<Movement[]>([])
  const [corridors, setCorridors] = useState<Corridor[]>([])
  const [loading, setLoading] = useState(true)
  const [layer, setLayer] = useState<'all' | 'cctv' | 'corridors'>('all')
  const [stats, setStats] = useState({ locations: 0, movements: 0, corridors: 0 })

  useEffect(() => {
    const init = async () => {
      try {
        // Load Leaflet dynamically
        if (!L) {
          L = (await import('leaflet')).default
          // Fix marker icons
          delete (L.Icon.Default.prototype as any)._getIconUrl
          L.Icon.Default.mergeOptions({
            iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
            iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
          })
        }

        // Fetch data in parallel
        const [locRes, movRes, corrRes] = await Promise.all([
          fetch('/api/geo/locations?limit=300').then(r => r.json()),
          fetch('/api/geo/movements?limit=200').then(r => r.json()),
          fetch('/api/geo/corridors').then(r => r.json()),
        ])

        const locs: Location[] = locRes.locations || []
        const movs: Movement[] = movRes.movements || []
        const corrs: Corridor[] = corrRes.corridors || []

        setLocations(locs)
        setMovements(movs)
        setCorridors(corrs)
        setStats({ locations: locs.length, movements: movs.length, corridors: corrs.length })
        setLoading(false)

        if (mapRef.current && !mapInstanceRef.current) {
          // Find center from locations with valid coordinates
          const validLocs = locs.filter(l => l.latitude && l.longitude)
          const center: [number, number] = validLocs.length > 0
            ? [validLocs[0].latitude, validLocs[0].longitude]
            : [20.5937, 78.9629] // India center

          const map = L.map(mapRef.current, {
            center,
            zoom: 6,
            zoomControl: true,
          })

          L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '© OpenStreetMap © CartoDB',
            subdomains: 'abcd',
            maxZoom: 19,
          }).addTo(map)

          mapInstanceRef.current = map

          // Add location markers
          const locGroup = L.layerGroup()
          validLocs.forEach(loc => {
            const color = loc.location_type === 'hotspot' ? '#ef4444' : loc.location_type === 'cctv' ? '#06b6d4' : '#10b981'
            const marker = L.circleMarker([loc.latitude, loc.longitude], {
              radius: 6,
              fillColor: color,
              color: color,
              weight: 1,
              opacity: 0.9,
              fillOpacity: 0.7,
            }).bindPopup(`
              <div style="color:#0f172a;font-family:Inter,sans-serif">
                <strong>${loc.location_name || 'Location'}</strong><br/>
                ${loc.area}, ${loc.city}<br/>
                <span style="font-size:11px;color:#64748b">${loc.location_id} | ${loc.location_type}</span>
              </div>
            `)
            locGroup.addLayer(marker)
          })
          locGroup.addTo(map)

          // Add CCTV/ANPR movement events as lines
          const anprGroup = L.layerGroup()
          // Group movements by plate for trajectory lines
          const byPlate: Record<string, Movement[]> = {}
          movs.forEach(m => {
            if (m.plate_number) {
              byPlate[m.plate_number] = byPlate[m.plate_number] || []
              byPlate[m.plate_number].push(m)
            }
          })

          // Draw lines between consecutive sightings
          Object.values(byPlate).forEach(plateMoves => {
            const coordMoves = plateMoves.filter(m => {
              const loc = validLocs.find(l => l.location_id === m.location_id)
              return loc?.latitude && loc?.longitude
            })
            if (coordMoves.length > 1) {
              const coords = coordMoves.map(m => {
                const loc = validLocs.find(l => l.location_id === m.location_id)!
                return [loc.latitude, loc.longitude] as [number, number]
              })
              L.polyline(coords, { color: '#f59e0b', weight: 1.5, opacity: 0.6, dashArray: '4,4' }).addTo(anprGroup)
            }
          })
          anprGroup.addTo(map)

          // Add high-risk corridors as circles
          const corrGroup = L.layerGroup()
          corrs.forEach(corr => {
            const loc = validLocs.find(l => l.location_id === corr.location_id)
            if (loc?.latitude && loc?.longitude) {
              L.circle([loc.latitude, loc.longitude], {
                radius: 8000,
                fillColor: '#ef4444',
                color: '#ef4444',
                weight: 1,
                opacity: 0.4,
                fillOpacity: 0.08,
              }).bindPopup(`
                <div style="color:#0f172a;font-family:Inter,sans-serif">
                  <strong>⚠ Surveillance Corridor</strong><br/>
                  ${corr.area}, ${corr.city}<br/>
                  Incidents: ${corr.incident_count} | Risk: ${corr.risk_score}<br/>
                  <span style="font-size:11px;color:#ef4444">High-density crime zone</span>
                </div>
              `).addTo(corrGroup)
            }
          })
          corrGroup.addTo(map)
        }
      } catch (e) {
        console.error('Geo error:', e)
        setLoading(false)
      }
    }

    init()
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: 'calc(100vh - 100px)' }}>
      {/* Header */}
      <div className="glass-panel" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <MapPin size={16} color="var(--accent)" />
        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-bright)' }}>Geospatial & Movement Intelligence</span>
        <span className="badge badge-default"><Eye size={10} style={{ display: 'inline' }} /> {stats.locations} Locations</span>
        <span className="badge badge-default" style={{ color: 'var(--amber)' }}>🚗 {stats.movements} ANPR Events</span>
        <span className="badge badge-default" style={{ color: 'var(--red)' }}>⚠ {stats.corridors} Corridors</span>
        {loading && <span style={{ fontSize: 12, color: 'var(--text-faint)' }}>Loading map data…</span>}
      </div>

      <div style={{ display: 'flex', gap: 12, flex: 1, minHeight: 0 }}>
        {/* Map */}
        <div style={{ flex: 1, borderRadius: 12, overflow: 'hidden', border: '1px solid var(--border)', position: 'relative' }}>
          <div ref={mapRef} id="leaflet-map" style={{ width: '100%', height: '100%' }} />
          {loading && (
            <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', background: 'rgba(7,10,18,0.9)', padding: '16px 24px', borderRadius: 8, color: 'var(--accent)', fontSize: 13 }}>
              Loading map…
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div style={{ width: 260, display: 'flex', flexDirection: 'column', gap: 12, overflowY: 'auto' }}>
          {/* Legend */}
          <div className="glass-panel" style={{ padding: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10 }}>Map Legend</div>
            {[
              { color: '#10b981', label: 'Standard Location' },
              { color: '#06b6d4', label: 'CCTV Camera' },
              { color: '#ef4444', label: 'High-Risk Hotspot' },
              { color: '#f59e0b', label: 'ANPR Vehicle Track' },
              { color: 'rgba(239,68,68,0.3)', label: 'Surveillance Corridor', border: '#ef4444' },
            ].map(item => (
              <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
                <div style={{ width: 12, height: 12, borderRadius: item.border ? 0 : '50%', background: item.color, border: item.border ? `2px solid ${item.border}` : 'none', flexShrink: 0 }} />
                <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{item.label}</span>
              </div>
            ))}
          </div>

          {/* Top Corridors */}
          {corridors.length > 0 && (
            <div className="glass-panel" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertTriangle size={11} color="var(--red)" /> High-Risk Corridors
              </div>
              {corridors.slice(0, 8).map((c, i) => (
                <div key={i} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                    <span style={{ fontSize: 12, color: 'var(--text)', flex: 1 }}>{c.area}, {c.city}</span>
                    <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--red)' }}>{c.risk_score?.toFixed(1)}</span>
                  </div>
                  <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                    <div style={{ height: '100%', borderRadius: 2, background: 'linear-gradient(90deg, #ef4444, #f59e0b)', width: `${Math.min(100, (c.risk_score || 0) * 10)}%` }} />
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-faint)', marginTop: 2 }}>{c.incident_count} incidents</div>
                </div>
              ))}
            </div>
          )}

          {/* Recent Sightings */}
          {movements.length > 0 && (
            <div className="glass-panel" style={{ padding: 14, flex: 1 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-faint)', textTransform: 'uppercase', marginBottom: 10 }}>Recent ANPR Sightings</div>
              {movements.slice(0, 10).map((m, i) => (
                <div key={i} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--amber)' }}>{m.plate_number || 'Unknown'}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{m.detection_type} • {m.timestamp?.slice(0, 16)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
