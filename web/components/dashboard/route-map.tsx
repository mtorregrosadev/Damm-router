"use client"

import { useEffect, useState, useRef, useCallback, useMemo } from "react"
import dynamic from "next/dynamic"
import { Truck, Clock, RotateCw, Play, Volume2, VolumeX, Map, GitBranch } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import type { RouteStop, RouteSummary } from "@/lib/types/route-data"

const MapContainer = dynamic(() => import("react-leaflet").then(m => m.MapContainer), { ssr: false })
const TileLayer    = dynamic(() => import("react-leaflet").then(m => m.TileLayer),    { ssr: false })
const Marker       = dynamic(() => import("react-leaflet").then(m => m.Marker),       { ssr: false })
const Popup        = dynamic(() => import("react-leaflet").then(m => m.Popup),        { ssr: false })
const Polyline     = dynamic(() => import("react-leaflet").then(m => m.Polyline),     { ssr: false })

const DEPOT_LAT = 41.5396
const DEPOT_LON =  2.2100

type EdgeState = "unvisited" | "active" | "visited" | "return"
type NodeState = "unvisited" | "active" | "visited" | "stop-reached"
type ViewMode  = "map" | "graph"

interface RouteMapProps {
  stops: RouteStop[]
  summary: RouteSummary | null
  selectedStop: number | null
  onSelectStop: (ordre: number | null) => void
}

interface SimulationNode {
  id: string
  lat: number
  lon: number
  type: "warehouse" | "stop"
  stopId?: number
  geometry?: [number, number][] // Road points leading to this node
}

// ── SVG Graph overlay ──────────────────────────────────────────────────────────

function GraphOverlay({
  map,
  nodes,
  edgeStates,
  nodeStates,
  simulationLines = [],
}: {
  map: import("leaflet").Map | null
  nodes: SimulationNode[]
  edgeStates: Record<string, EdgeState>
  nodeStates: Record<string, NodeState>
  simulationLines?: {from: string, to: string, opacity: number}[]
}) {
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({})
  const [geomPaths, setGeomPaths] = useState<Record<string, string>>({})

  const updatePositions = useCallback(() => {
    if (!map) return
    const nextPos: Record<string, { x: number; y: number }> = {}
    const nextPaths: Record<string, string> = {}
    
    nodes.forEach(node => {
      const pt = map.latLngToLayerPoint([node.lat, node.lon])
      nextPos[node.id] = { x: pt.x, y: pt.y }
      
      if (node.geometry && node.geometry.length > 0) {
        const pathData = node.geometry.map((coord, i) => {
          const p = map.latLngToLayerPoint(coord as [number, number])
          return `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
        }).join(' ')
        nextPaths[node.id] = pathData
      }
    })
    setPositions(nextPos)
    setGeomPaths(nextPaths)
  }, [map, nodes])

  useEffect(() => {
    if (!map) return
    updatePositions()
    map.on("move zoom viewreset", updatePositions)
    return () => { map.off("move zoom viewreset", updatePositions) }
  }, [map, updatePositions])

  if (Object.keys(positions).length === 0) return null

  return (
    <svg className="pointer-events-none absolute inset-0 z-[500]" style={{ width: "100%", height: "100%" }}>
      <defs>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3.5" result="coloredBlur" />
          <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Simulation "mil linies" Arcs - NOW MUCH DENSER */}
      {simulationLines.map((line, idx) => {
        const from = positions[line.from]; const to = positions[line.to]
        if (!from || !to) return null
        const dx = to.x - from.x; const dy = to.y - from.y
        const dr = Math.sqrt(dx * dx + dy * dy) * (0.6 + Math.random() * 0.8)
        const sweep = Math.random() > 0.5 ? 1 : 0
        return (
          <path key={`sim-${idx}`} 
            d={`M ${from.x} ${from.y} A ${dr} ${dr} 0 0 ${sweep} ${to.x} ${to.y}`}
            fill="none" stroke="#FFBF00" strokeWidth={1 + Math.random() * 2} opacity={line.opacity * 0.5}
            strokeLinecap="round" filter="url(#glow)" />
        )
      })}

      {/* Actual Route Edges - FOLLOWING ROADS */}
      {nodes.map((node, i) => {
        if (i === 0) return null // Skip first node (warehouse has no incoming geometry)
        const key = `${nodes[i-1].id}-${node.id}`
        const state = edgeStates[key] || "unvisited"
        if (state === "unvisited") return null

        const pathData = geomPaths[node.id]
        if (!pathData) {
          // Fallback to straight line if no geometry
          const from = positions[nodes[i-1].id]; const to = positions[node.id]
          if (!from || !to) return null
          return (
            <line key={key} x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke={state === "active" ? "#FFBF00" : "#E30613"} 
              strokeWidth={state === "active" ? 5 : 3.5} 
              opacity={state === "active" ? 1 : 0.9}
              strokeLinecap="round" filter={state === "active" ? "url(#glow)" : undefined}
              className={state === "active" ? "animate-pulse" : ""} />
          )
        }

        return (
          <path key={key} d={pathData}
            fill="none" stroke={state === "active" ? "#FFBF00" : "#E30613"}
            strokeWidth={state === "active" ? 5 : 3.5}
            opacity={state === "active" ? 1 : 0.9}
            strokeLinecap="round" filter={state === "active" ? "url(#glow)" : undefined}
            className={state === "active" ? "animate-pulse" : ""} />
        )
      })}

      {/* Nodes */}
      {nodes.map(node => {
        const pos = positions[node.id]; if (!pos) return null
        const state = nodeStates[node.id] || "unvisited"
        const isWarehouse = node.type === "warehouse"
        
        return (
          <g key={node.id}>
            <circle cx={pos.x} cy={pos.y} 
              r={isWarehouse ? 12 : state === "stop-reached" ? 10 : 5} 
              fill={isWarehouse ? "#FFBF00" : (state === "stop-reached" || state === "visited") ? "#E30613" : "#9CA3AF"}
              stroke="white" strokeWidth={2.5}
              className={state === "active" ? "animate-ping" : ""} />
            {node.stopId && (
              <text x={pos.x} y={pos.y} textAnchor="middle" dominantBaseline="central"
                fill="white" fontSize={11} fontWeight="800">
                {node.stopId}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

// ── Map event handler ──────────────────────────────────────────────────────────

function MapEvents({ onMapReady }: { onMapReady: (map: import("leaflet").Map) => void }) {
  const MapHook = dynamic(
    () => import("react-leaflet").then(mod => {
      const Component = () => {
        const map = mod.useMap()
        useEffect(() => { onMapReady(map) }, [map])
        return null
      }
      return Component
    }),
    { ssr: false }
  )
  return <MapHook />
}

// ── Main component ─────────────────────────────────────────────────────────────

function formatMinutes(totalMin: number): string {
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  if (h > 0) {
    return m > 0 ? `${h}h ${m}min` : `${h}h`
  }
  return `${m}min`
}

export function RouteMap({ stops, summary, selectedStop, onSelectStop }: RouteMapProps) {
  const { t } = useLanguage()
  const [isMounted, setIsMounted] = useState(false)
  const [L, setL] = useState<typeof import("leaflet") | null>(null)
  const [mapInstance, setMapInstance] = useState<import("leaflet").Map | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>("map")

  // DFS animation state
  const [edgeStates, setEdgeStates] = useState<Record<string, EdgeState>>({})
  const [nodeStates, setNodeStates] = useState<Record<string, NodeState>>({})
  const [isPlaying, setIsPlaying] = useState(false)
  const [isSimulating, setIsSimulating] = useState(false)
  const [simulationLines, setSimulationLines] = useState<{from: string, to: string, opacity: number}[]>([])
  const [speed, setSpeed] = useState(150)
  const [soundOn, setSoundOn] = useState(true)
  const audioContextRef = useRef<AudioContext | null>(null)

  // Derive simulation nodes from actual stops with geometry
  const simNodes = useMemo<SimulationNode[]>(() => {
    const nodes: SimulationNode[] = [{ id: "wh-start", lat: DEPOT_LAT, lon: DEPOT_LON, type: "warehouse" }]
    
    // Unique stops by order
    const seen = new Set<number>()
    stops.forEach(s => {
      if (!seen.has(s.ordre)) {
        nodes.push({ 
          id: `s-${s.ordre}`, 
          lat: s.lat, 
          lon: s.lon, 
          type: "stop", 
          stopId: s.ordre,
          geometry: s.geometria as [number, number][]
        })
        seen.add(s.ordre)
      }
    })
    
    // Last stop return to warehouse
    nodes.push({ id: "wh-end", lat: DEPOT_LAT, lon: DEPOT_LON, type: "warehouse" })
    return nodes
  }, [stops])

  useEffect(() => {
    setIsMounted(true)
    import("leaflet").then(leaflet => setL(leaflet.default))
    import("leaflet/dist/leaflet.css")
  }, [])

  const playAlgoBeep = useCallback((isStop: boolean) => {
    if (!soundOn) return
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()
    }
    const ctx = audioContextRef.current
    if (ctx.state === 'suspended') ctx.resume()
    const osc = ctx.createOscillator(); const gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.value = isStop ? 500 : 900
    gain.gain.setValueAtTime(0, ctx.currentTime)
    gain.gain.linearRampToValueAtTime(0.06, ctx.currentTime + 0.01)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12)
    osc.start(); osc.stop(ctx.currentTime + 0.15)
  }, [soundOn])

  const playSimSound = useCallback(() => {
    if (!soundOn) return
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()
    }
    const ctx = audioContextRef.current
    if (ctx.state === 'suspended') ctx.resume()
    const osc = ctx.createOscillator(); const gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.value = 1200 + Math.random() * 3000
    gain.gain.setValueAtTime(0, ctx.currentTime)
    gain.gain.linearRampToValueAtTime(0.03, ctx.currentTime + 0.005)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.015)
    osc.start(); osc.stop(ctx.currentTime + 0.02)
  }, [soundOn])

  const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

  const startAnimation = useCallback(async () => {
    setIsPlaying(true)
    setEdgeStates({})
    setNodeStates({ "wh-start": "visited" })
    
    for (let i = 0; i < simNodes.length - 1; i++) {
      const from = simNodes[i]; const to = simNodes[i+1]
      const key = `${from.id}-${to.id}`
      
      setEdgeStates(prev => ({ ...prev, [key]: "active" }))
      setNodeStates(prev => ({ ...prev, [to.id]: "active" }))
      playAlgoBeep(to.type === "stop")
      
      await sleep(speed)
      
      setEdgeStates(prev => ({ ...prev, [key]: "visited" }))
      setNodeStates(prev => ({ ...prev, [to.id]: to.type === "stop" ? "stop-reached" : "visited" }))
    }
    setIsPlaying(false)
  }, [simNodes, speed, playAlgoBeep])

  const runShowcase = useCallback(async () => {
    setIsSimulating(true)
    setIsPlaying(true)
    setEdgeStates({})
    setNodeStates({})
    
    const iterations = 60 // MORE ITERATIONS
    for (let i = 0; i < iterations; i++) {
      const newLines = []
      const density = 25 // MORE LINES PER STEP
      for (let j = 0; j < density; j++) {
        const n1 = simNodes[Math.floor(Math.random() * simNodes.length)]
        const n2 = simNodes[Math.floor(Math.random() * simNodes.length)]
        if (n1.id !== n2.id) newLines.push({ from: n1.id, to: n2.id, opacity: Math.random() })
      }
      setSimulationLines(newLines)
      playSimSound()
      await sleep(40) // FASTER
    }
    
    setSimulationLines([])
    setIsSimulating(false)
    await startAnimation()
  }, [simNodes, startAnimation, playSimSound])

  const resetAnimation = useCallback(() => {
    setEdgeStates({})
    setNodeStates({})
    setSimulationLines([])
    setIsPlaying(false)
    setIsSimulating(false)
  }, [])

  if (!isMounted || !L) {
    return (
      <div className="relative flex h-full w-full items-center justify-center bg-white">
        <div className="text-gray-400">Loading map...</div>
      </div>
    )
  }

  // ── Icon factories ────────────────────────────────────────────────────────────

  const createStopIcon = (ordre: number, isSelected: boolean, foraDeFranja: boolean) =>
    L.divIcon({
      className: "custom-marker",
      html: `<div style="
        width:28px;height:28px;
        background:${isSelected ? "#FFBF00" : foraDeFranja ? "#FFBF00" : "#E30613"};
        border-radius:50%;display:flex;align-items:center;justify-content:center;
        color:white;font-weight:bold;font-size:12px;
        border:2px solid ${isSelected ? "#FFBF00" : foraDeFranja ? "#FFBF00" : "#A5040D"};
        box-shadow:0 2px 4px rgba(0,0,0,0.2);">
        ${foraDeFranja && !isSelected ? '⚠' : ordre}
      </div>`,
      iconSize: [28, 28], iconAnchor: [14, 14],
    })

  const warehouseIcon = L.divIcon({
    className: "custom-marker",
    html: `<div style="width:32px;height:32px;background:#FFBF00;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#0B0F1C;font-weight:bold;font-size:14px;border:2px solid #FFBF00;box-shadow:0 2px 4px rgba(0,0,0,0.2);">W</div>`,
    iconSize: [32, 32], iconAnchor: [16, 16],
  })

  // ── Map center & route coords ─────────────────────────────────────────────────

  const center: [number, number] = stops.length > 0
    ? [
        stops.reduce((s, p) => s + p.lat, 0) / stops.length,
        stops.reduce((s, p) => s + p.lon, 0) / stops.length,
      ]
    : [DEPOT_LAT, DEPOT_LON]

  const stopsAmbGeometria = stops.filter(s => s.geometria.length > 0)
  const hasRealGeometry   = stopsAmbGeometria.length > 0

  const seenOrdres = new Set<number>()
  const uniqueStops = stops.filter(s => {
    if (seenOrdres.has(s.ordre)) return false
    seenOrdres.add(s.ordre)
    return true
  })
  const lastStop = uniqueStops[uniqueStops.length - 1]

  const routeCoords: [number, number][] = [
    [DEPOT_LAT, DEPOT_LON],
    ...uniqueStops.map(s => [s.lat, s.lon] as [number, number]),
    [DEPOT_LAT, DEPOT_LON],
  ]

  const returnCoords: [number, number][] = lastStop
    ? [[lastStop.lat, lastStop.lon], [DEPOT_LAT, DEPOT_LON]]
    : []

  const kpiStops = summary ? `${summary.clients_visitats} ${t.dashboard.stops}` : "—"
  const kpiTime  = summary ? formatMinutes(summary.temps_total_min) : "—"

  return (
    <div className="relative h-full w-full">
      {/* View Toggle */}
      <div className="absolute left-1/2 top-3 z-[1000] flex -translate-x-1/2 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <button
          onClick={() => setViewMode("map")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${viewMode === "map" ? "bg-[#E30613] text-white" : "text-gray-500 hover:text-gray-700"}`}
        >
          <Map className="h-4 w-4" />
          Mapa
        </button>
        <button
          onClick={() => setViewMode("graph")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${viewMode === "graph" ? "bg-[#E30613] text-white" : "text-gray-500 hover:text-gray-700"}`}
        >
          <GitBranch className="h-4 w-4" />
          Graf DFS
        </button>
      </div>

      {/* DFS Controls */}
      {viewMode === "graph" && (
        <div className="absolute right-3 top-3 z-[1000] flex flex-col gap-2 rounded-lg border border-gray-200 bg-white/95 p-3 shadow-lg backdrop-blur-sm">
          <div className="flex flex-col gap-2">
            <button
              onClick={runShowcase} disabled={isPlaying}
              className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-bold transition-colors ${isPlaying ? "cursor-not-allowed bg-gray-100 text-gray-400" : "bg-[#E30613] text-white hover:bg-[#A5040D] shadow-md shadow-red-100"}`}
            >
              <Play className="h-4 w-4" /> Showcase OR-Tools
            </button>
            <div className="flex gap-2">
              <button
                onClick={startAnimation} disabled={isPlaying}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${isPlaying ? "cursor-not-allowed bg-gray-100 text-gray-400" : "border border-gray-200 text-gray-600 hover:bg-gray-50"}`}
              >
                Només ruta
              </button>
              <button onClick={resetAnimation} className="flex items-center justify-center rounded-lg border border-gray-200 px-3 py-1.5 text-gray-600 transition-colors hover:bg-gray-50">
                <RotateCw className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          
          {isSimulating && (
            <div className="flex items-center gap-2 px-2 py-1 bg-amber-50 rounded border border-amber-200 animate-pulse">
              <div className="h-2 w-2 rounded-full bg-[#FFBF00] animate-ping" />
              <span className="text-[10px] font-bold text-[#FFBF00] uppercase tracking-wider">Algoritme explorant milions de camins...</span>
            </div>
          )}

          <div className="flex gap-1 mt-1">
            {([300, 150, 50] as const).map((s, i) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={`flex-1 rounded px-2 py-1 text-[10px] font-medium transition-colors ${speed === s ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
                {["Lent", "Normal", "Ràpid"][i]}
              </button>
            ))}
          </div>
          <button onClick={() => setSoundOn(!soundOn)}
            className={`flex items-center justify-center gap-2 rounded-lg py-1.5 text-[10px] transition-colors ${soundOn ? "bg-gray-100 text-gray-700" : "border border-gray-200 text-gray-400"}`}>
            {soundOn ? <Volume2 className="h-3.5 w-3.5" /> : <VolumeX className="h-3.5 w-3.5" />}
            {soundOn ? "So activat" : "So desactivat"}
          </button>
        </div>
      )}

      <MapContainer center={center} zoom={12} style={{ height: "100%", width: "100%" }} zoomControl>
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        <MapEvents onMapReady={setMapInstance} />

        {viewMode === "map" && (
          <>
            <Marker position={[DEPOT_LAT, DEPOT_LON]} icon={warehouseIcon}>
              <Popup>
                <div className="min-w-[180px]">
                  <p className="font-bold">{t.dashboard.warehouse}</p>
                  <p className="text-muted-foreground text-sm">{summary?.ruta ?? ""}</p>
                </div>
              </Popup>
            </Marker>

            {stops.map((stop, idx) => (
              <Marker
                key={`${stop.ordre}-${idx}`}
                position={[stop.lat, stop.lon]}
                icon={createStopIcon(stop.ordre, selectedStop === stop.ordre, stop.fora_franja)}
                eventHandlers={{ click: () => onSelectStop(selectedStop === stop.ordre ? null : stop.ordre) }}
              >
                <Popup>
                  <StopPopup stop={stop} t={t} />
                </Popup>
              </Marker>
            ))}

            {hasRealGeometry
              ? stopsAmbGeometria.map((stop, idx) => (
                  <Polyline
                    key={`geo-${stop.ordre}-${idx}`}
                    positions={stop.geometria}
                    color="#E30613"
                    weight={4}
                    opacity={0.8}
                  />
                ))
              : routeCoords.length > 2 && (
                  <Polyline positions={routeCoords} color="#E30613" weight={4} opacity={0.8} />
                )
            }

            {returnCoords.length === 2 && (
              <Polyline positions={returnCoords} color="#FFBF00" weight={3} opacity={0.6} dashArray="10, 10" />
            )}
          </>
        )}
      </MapContainer>

      {/* Synchronized DFS Graph Overlay WITH ROAD GEOMETRY */}
      {viewMode === "graph" && (
        <GraphOverlay 
          map={mapInstance} 
          nodes={simNodes}
          edgeStates={edgeStates} 
          nodeStates={nodeStates} 
          simulationLines={simulationLines} 
        />
      )}

      {/* KPI bar */}
      <div className="absolute bottom-4 left-1/2 z-[1000] flex -translate-x-1/2 gap-3">
        <KPICard icon={<Truck className="h-4 w-4" />} value={kpiStops} />
        <KPICard icon={<Clock className="h-4 w-4" />} value={kpiTime} />
      </div>
    </div>
  )
}

function StopPopup({ stop, t }: { stop: RouteStop; t: ReturnType<typeof useLanguage>["t"] }) {
  return (
    <div className="min-w-[200px]">
      <p className="font-bold text-gray-900">{stop.nom}</p>
      <p className="text-sm text-gray-500">{stop.zona}</p>
      <div className="mt-2 border-t border-gray-100 pt-2 space-y-1">
        <p className="text-xs text-gray-500">
          <Clock className="mr-1 inline h-3 w-3" />{stop.hora}
        </p>
        {stop.temps_descarrega > 0 && (
          <p className="text-xs text-gray-500">{stop.temps_descarrega} {t.stops.unloadTime}</p>
        )}
        {stop.parada_compartida !== null && (
          <span className="inline-block rounded-full bg-amber-50 px-2 py-0.5 text-[10px] text-[#FFBF00] border border-amber-100">
            #{stop.parada_compartida} {t.stops.sharedStop}
          </span>
        )}
        {stop.fora_franja && (
          <span className="inline-block rounded-full bg-red-50 px-2 py-0.5 text-[10px] text-[#E30613] border border-red-100">
            ⚠ {t.stops.outOfWindow}
          </span>
        )}
      </div>
    </div>
  )
}

function KPICard({ icon, value }: { icon: React.ReactNode; value: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white/90 px-4 py-2 shadow-md backdrop-blur-sm">
      <span className="text-[#E30613]">{icon}</span>
      <span className="text-sm font-bold text-[#374151]" style={{ fontFamily: 'var(--font-title)', textTransform: 'uppercase' }}>{value}</span>
    </div>
  )
}
