"use client"

import { useEffect, useState, useRef, useCallback } from "react"
import dynamic from "next/dynamic"
import { Truck, Clock, RotateCw, Play, Volume2, VolumeX, Map, GitBranch } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { graphNodes, graphEdges, routePath, getNodeById, getEdgeKey, type GraphNode } from "@/lib/graph-data"
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

// ── SVG DFS graph overlay ──────────────────────────────────────────────────────

function GraphOverlay({
  map,
  edgeStates,
  nodeStates,
}: {
  map: import("leaflet").Map | null
  edgeStates: Record<string, EdgeState>
  nodeStates: Record<string, NodeState>
}) {
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({})

  const updatePositions = useCallback(() => {
    if (!map) return
    const next: Record<string, { x: number; y: number }> = {}
    graphNodes.forEach(node => {
      const pt = map.latLngToLayerPoint([node.lat, node.lng])
      next[node.id] = { x: pt.x, y: pt.y }
    })
    setPositions(next)
  }, [map])

  useEffect(() => {
    if (!map) return
    updatePositions()
    map.on("move", updatePositions)
    map.on("zoom", updatePositions)
    return () => { map.off("move", updatePositions); map.off("zoom", updatePositions) }
  }, [map, updatePositions])

  const getEdgeStyle = (state: EdgeState, isReturn: boolean) => {
    switch (state) {
      case "active":   return { stroke: "var(--amber)", strokeWidth: 3, opacity: 1, dashArray: undefined }
      case "visited":  return { stroke: "var(--red)",   strokeWidth: 2.5, opacity: 0.85, dashArray: undefined }
      case "return":   return { stroke: "var(--gray-mid)", strokeWidth: 1.5, opacity: 0.8, dashArray: "4 3" }
      default:         return { stroke: "var(--gray-light)", strokeWidth: 1, opacity: 0.3, dashArray: isReturn ? "4 3" : undefined }
    }
  }

  const getNodeStyle = (node: GraphNode, state: NodeState) => {
    if (node.type === "warehouse") return { r: 14, fill: "var(--amber)", stroke: "var(--amber)", strokeWidth: 2 }
    switch (state) {
      case "active":       return { r: 6, fill: "var(--amber)", stroke: "var(--amber)", strokeWidth: 0 }
      case "visited":      return { r: 4, fill: "var(--red)", stroke: "none", strokeWidth: 0 }
      case "stop-reached": return { r: 14, fill: "var(--red)", stroke: "var(--red-dark)", strokeWidth: 2 }
      default:             return { r: node.type === "stop" ? 8 : 3, fill: node.type === "stop" ? "var(--charcoal)" : "var(--gray-mid)", stroke: node.type === "stop" ? "var(--gray-mid)" : "none", strokeWidth: node.type === "stop" ? 2 : 0 }
    }
  }

  if (Object.keys(positions).length === 0) return null

  return (
    <svg className="pointer-events-none absolute inset-0 z-[500]" style={{ width: "100%", height: "100%" }}>
      <defs>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {graphEdges.map(edge => {
        const from = positions[edge.from]; const to = positions[edge.to]
        if (!from || !to) return null
        const key = getEdgeKey(edge.from, edge.to)
        const state = edgeStates[key] || "unvisited"
        const style = getEdgeStyle(state, !!edge.isReturn)
        return (
          <line key={key} x1={from.x} y1={from.y} x2={to.x} y2={to.y}
            stroke={style.stroke} strokeWidth={style.strokeWidth} opacity={style.opacity}
            strokeDasharray={style.dashArray} strokeLinecap="round"
            className={state === "active" ? "animate-pulse" : ""}
            filter={state === "active" ? "url(#glow)" : undefined} />
        )
      })}

      {graphNodes.map(node => {
        const pos = positions[node.id]; if (!pos) return null
        const state = nodeStates[node.id] || "unvisited"
        const style = getNodeStyle(node, state)
        return (
          <g key={node.id} className={state === "active" ? "animate-pulse" : ""}>
            <circle cx={pos.x} cy={pos.y} r={style.r} fill={style.fill}
              stroke={style.stroke} strokeWidth={style.strokeWidth}
              filter={state === "active" ? "url(#glow)" : undefined} />
            {(state === "stop-reached" || (node.type === "stop" && state === "unvisited")) && node.stopId && (
              <text x={pos.x} y={pos.y} textAnchor="middle" dominantBaseline="central"
                fill="white" fontSize={state === "stop-reached" ? 11 : 9} fontWeight="bold">
                {node.stopId}
              </text>
            )}
            {node.type === "warehouse" && (
              <text x={pos.x} y={pos.y} textAnchor="middle" dominantBaseline="central"
                fill="#0B0F1C" fontSize={12} fontWeight="bold">W</text>
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
  const [speed, setSpeed] = useState(150)
  const [soundOn, setSoundOn] = useState(true)
  const audioContextRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    setIsMounted(true)
    import("leaflet").then(leaflet => setL(leaflet.default))
    import("leaflet/dist/leaflet.css")
  }, [])

  const playAlgoBeep = useCallback((nodeIndex: number, totalNodes: number) => {
    if (!soundOn) return
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as typeof window & { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
    }
    const ctx = audioContextRef.current
    const isStop = nodeIndex > 0 && nodeIndex < totalNodes - 1
    if (isStop) {
      const osc1 = ctx.createOscillator(); const osc2 = ctx.createOscillator(); const gain = ctx.createGain()
      osc1.connect(gain); osc2.connect(gain); gain.connect(ctx.destination)
      osc1.type = 'sine'; osc1.frequency.value = 520
      osc2.type = 'sine'; osc2.frequency.value = 780
      gain.gain.setValueAtTime(0, ctx.currentTime)
      gain.gain.linearRampToValueAtTime(0.18, ctx.currentTime + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1)
      osc1.start(ctx.currentTime); osc1.stop(ctx.currentTime + 0.06)
      osc2.start(ctx.currentTime); osc2.stop(ctx.currentTime + 0.1)
    } else {
      const osc = ctx.createOscillator(); const gain = ctx.createGain()
      osc.connect(gain); gain.connect(ctx.destination)
      osc.type = 'sine'; osc.frequency.value = 1200
      gain.gain.setValueAtTime(0, ctx.currentTime)
      gain.gain.linearRampToValueAtTime(0.06, ctx.currentTime + 0.005)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.02)
      osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.02)
    }
  }, [soundOn])

  const playCompletionChord = useCallback(() => {
    if (!soundOn) return
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as typeof window & { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
    }
    const ctx = audioContextRef.current
    const notes = [523, 659, 784, 1046]
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator(); const gain = ctx.createGain()
      osc.connect(gain); gain.connect(ctx.destination)
      osc.type = 'sine'; osc.frequency.value = freq
      gain.gain.setValueAtTime(0, ctx.currentTime + i * 0.08)
      gain.gain.linearRampToValueAtTime(0.12, ctx.currentTime + i * 0.08 + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.08 + 0.2)
      osc.start(ctx.currentTime + i * 0.08); osc.stop(ctx.currentTime + i * 0.08 + 0.2)
    })
  }, [soundOn])

  const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

  const startAnimation = useCallback(async () => {
    setIsPlaying(true)
    setEdgeStates({})
    setNodeStates({ wh: "visited" })
    for (let i = 0; i < routePath.length - 1; i++) {
      const fromId = routePath[i]; const toId = routePath[i + 1]
      const edgeKey = getEdgeKey(fromId, toId); const toNode = getNodeById(toId)
      setEdgeStates(prev => ({ ...prev, [edgeKey]: "active" }))
      setNodeStates(prev => ({ ...prev, [toId]: "active" }))
      playAlgoBeep(i + 1, routePath.length)
      await sleep(100)
      const isReturn = graphEdges.find(e => e.from === fromId && e.to === toId)?.isReturn
      setEdgeStates(prev => ({ ...prev, [edgeKey]: isReturn ? "return" : "visited" }))
      setNodeStates(prev => ({ ...prev, [toId]: toNode?.type === "stop" ? "stop-reached" : "visited" }))
    }
    playCompletionChord()
    setIsPlaying(false)
  }, [speed, playAlgoBeep, playCompletionChord])

  const resetAnimation = useCallback(() => {
    setEdgeStates({})
    setNodeStates({})
    setIsPlaying(false)
  }, [])

  if (!isMounted || !L) {
    return (
      <div className="relative flex h-full w-full items-center justify-center bg-background">
        <div className="text-muted-foreground">Loading map...</div>
      </div>
    )
  }

  // ── Icon factories ────────────────────────────────────────────────────────────

  const createStopIcon = (ordre: number, isSelected: boolean, foraDeFranja: boolean) =>
    L.divIcon({
      className: "custom-marker",
      html: `<div style="
        width:28px;height:28px;
        background:${isSelected ? "var(--amber)" : foraDeFranja ? "var(--amber)" : "var(--red)"};
        border-radius:50%;display:flex;align-items:center;justify-content:center;
        color:white;font-weight:bold;font-size:12px;
        border:2px solid ${isSelected ? "var(--amber)" : foraDeFranja ? "var(--amber)" : "var(--red-dark)"};
        box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        ${foraDeFranja && !isSelected ? '⚠' : ordre}
      </div>`,
      iconSize: [28, 28], iconAnchor: [14, 14],
    })

  const warehouseIcon = L.divIcon({
    className: "custom-marker",
    html: `<div style="width:32px;height:32px;background:var(--amber);border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--black);font-weight:bold;font-size:14px;border:2px solid var(--amber);box-shadow:0 1px 3px rgba(0,0,0,0.08);">W</div>`,
    iconSize: [32, 32], iconAnchor: [16, 16],
  })

  // ── Map center & route coords ─────────────────────────────────────────────────

  const center: [number, number] = stops.length > 0
    ? [
        stops.reduce((s, p) => s + p.lat, 0) / stops.length,
        stops.reduce((s, p) => s + p.lon, 0) / stops.length,
      ]
    : [DEPOT_LAT, DEPOT_LON]

  // Stops amb geometria real (primer membre de cada grup compartit)
  const stopsAmbGeometria = stops.filter(s => s.geometria.length > 0)
  const hasRealGeometry   = stopsAmbGeometria.length > 0

  // Per al marcador de l'última parada i el tram de retorn
  const seenOrdres = new Set<number>()
  const uniqueStops = stops.filter(s => {
    if (seenOrdres.has(s.ordre)) return false
    seenOrdres.add(s.ordre)
    return true
  })
  const lastStop = uniqueStops[uniqueStops.length - 1]

  // Fallback (sense geometria): línia recta dipòsit → parades → dipòsit
  const routeCoords: [number, number][] = [
    [DEPOT_LAT, DEPOT_LON],
    ...uniqueStops.map(s => [s.lat, s.lon] as [number, number]),
    [DEPOT_LAT, DEPOT_LON],
  ]

  // Tram de retorn: línia discontínua (la geometria del retorn no s'emmagatzema a ruta_punts)
  const returnCoords: [number, number][] = lastStop
    ? [[lastStop.lat, lastStop.lon], [DEPOT_LAT, DEPOT_LON]]
    : []

  // ── KPI values ────────────────────────────────────────────────────────────────

  const kpiStops = summary ? `${summary.clients_visitats} ${t.dashboard.stops}` : "—"
  const kpiTime  = summary ? `${summary.temps_total_min} min` : "—"
  const kpiSkip  = summary && summary.clients_saltats > 0
    ? `${summary.clients_saltats} ${t.stops.skipped}`
    : null

  return (
    <div className="relative h-full w-full">
      {/* View Toggle */}
      <div className="absolute left-1/2 top-3 z-[1000] flex -translate-x-1/2 overflow-hidden rounded-lg border border-border bg-card">
        <button
          onClick={() => setViewMode("map")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${viewMode === "map" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
        >
          <Map className="h-4 w-4" />
          Mapa
        </button>
        <button
          onClick={() => setViewMode("graph")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${viewMode === "graph" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
        >
          <GitBranch className="h-4 w-4" />
          Graf DFS
        </button>
      </div>

      {/* DFS Controls */}
      {viewMode === "graph" && (
        <div className="absolute right-3 top-3 z-[1000] flex flex-col gap-2 rounded-lg border border-border bg-card/95 p-3 backdrop-blur-sm">
          <div className="flex gap-2">
            <button
              onClick={startAnimation} disabled={isPlaying}
              className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isPlaying ? "cursor-not-allowed bg-muted text-muted-foreground" : "bg-primary text-primary-foreground hover:bg-primary/90"}`}
            >
              <Play className="h-4 w-4" /> Iniciar ruta
            </button>
            <button onClick={resetAnimation} className="flex items-center justify-center rounded-lg border border-border px-3 py-2 text-muted-foreground transition-colors hover:border-muted-foreground hover:text-foreground">
              <RotateCw className="h-4 w-4" />
            </button>
          </div>
          <div className="flex gap-1">
            {([300, 150, 50] as const).map((s, i) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={`flex-1 rounded px-2 py-1 text-xs font-medium transition-colors ${speed === s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-foreground"}`}>
                {["Lent", "Normal", "Ràpid"][i]}
              </button>
            ))}
          </div>
          <button onClick={() => setSoundOn(!soundOn)}
            className={`flex items-center justify-center gap-2 rounded-lg py-1.5 text-xs transition-colors ${soundOn ? "bg-muted text-foreground" : "border border-border text-muted-foreground"}`}>
            {soundOn ? <Volume2 className="h-3.5 w-3.5" /> : <VolumeX className="h-3.5 w-3.5" />}
            {soundOn ? "So activat" : "So desactivat"}
          </button>
        </div>
      )}

      <MapContainer center={center} zoom={12} style={{ height: "100%", width: "100%" }} zoomControl>
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        <MapEvents onMapReady={setMapInstance} />

        {viewMode === "map" && (
          <>
            {/* Depot / warehouse */}
            <Marker position={[DEPOT_LAT, DEPOT_LON]} icon={warehouseIcon}>
              <Popup>
                <div className="min-w-[180px]">
                  <p className="font-bold">{t.dashboard.warehouse}</p>
                  <p className="text-muted-foreground text-sm">{summary?.ruta ?? ""}</p>
                </div>
              </Popup>
            </Marker>

            {/* Client stops */}
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

            {/* Polilínies reals per tram (geometria OSRM) */}
            {hasRealGeometry
              ? stopsAmbGeometria.map((stop, idx) => (
                  <Polyline
                    key={`geo-${stop.ordre}-${idx}`}
                    positions={stop.geometria}
                    color="var(--red)"
                    weight={3}
                    opacity={0.8}
                  />
                ))
              : routeCoords.length > 2 && (
                  // Fallback: línia recta si no hi ha geometria OSRM
                  <Polyline positions={routeCoords} color="var(--red)" weight={3} opacity={0.8} />
                )
            }

            {/* Tram de retorn al dipòsit: línia discontínua */}
            {returnCoords.length === 2 && (
              <Polyline positions={returnCoords} color="var(--amber)" weight={2} opacity={0.6} dashArray="10, 10" />
            )}
          </>
        )}
      </MapContainer>

      {/* DFS overlay */}
      {viewMode === "graph" && (
        <GraphOverlay map={mapInstance} edgeStates={edgeStates} nodeStates={nodeStates} />
      )}

      {/* KPI bar */}
      <div className="absolute bottom-4 left-1/2 z-[1000] flex -translate-x-1/2 gap-3">
        <KPICard icon={<Truck className="h-4 w-4" />} value={kpiStops} />
        <KPICard icon={<Clock className="h-4 w-4" />} value={kpiTime} />
        {kpiSkip && <KPICard icon={<span>⚠</span>} value={kpiSkip} />}
      </div>
    </div>
  )
}

function StopPopup({ stop, t }: { stop: RouteStop; t: ReturnType<typeof useLanguage>["t"] }) {
  return (
    <div className="min-w-[200px]">
      <p className="font-bold text-foreground">{stop.nom}</p>
      <p className="text-sm text-muted-foreground">{stop.zona}</p>
      <div className="mt-2 border-t border-border pt-2 space-y-1">
        <p className="text-xs text-muted-foreground">
          <Clock className="mr-1 inline h-3 w-3" />{stop.hora}
        </p>
        {stop.temps_descarrega > 0 && (
          <p className="text-xs text-muted-foreground">{stop.temps_descarrega} {t.stops.unloadTime}</p>
        )}
        {stop.parada_compartida !== null && (
          <span className="inline-block rounded-full bg-amber-light px-2 py-0.5 text-[10px] text-amber">
            #{stop.parada_compartida} {t.stops.sharedStop}
          </span>
        )}
        {stop.fora_franja && (
          <span className="inline-block rounded-full px-2 py-0.5 text-[10px]" style={{ background: 'var(--red-light)', color: 'var(--red)' }}>
            ⚠ {t.stops.outOfWindow}
          </span>
        )}
      </div>
    </div>
  )
}

function KPICard({ icon, value }: { icon: React.ReactNode; value: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-card/90 px-4 py-2 backdrop-blur-sm">
      <span className="text-primary">{icon}</span>
      <span className="text-sm font-medium text-foreground" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>{value}</span>
    </div>
  )
}
