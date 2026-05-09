"use client"

import { useEffect, useState, useRef, useCallback } from "react"
import dynamic from "next/dynamic"
import { Truck, Package, Clock, RotateCcw, Play, RotateCw, Volume2, VolumeX, Map, GitBranch } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { routeData, type Stop } from "@/lib/mock-data"
import { graphNodes, graphEdges, routePath, getNodeById, getEdgeKey, type GraphNode } from "@/lib/graph-data"

// Dynamically import Leaflet components to avoid SSR issues
const MapContainer = dynamic(
  () => import("react-leaflet").then((mod) => mod.MapContainer),
  { ssr: false }
)
const TileLayer = dynamic(
  () => import("react-leaflet").then((mod) => mod.TileLayer),
  { ssr: false }
)
const Marker = dynamic(
  () => import("react-leaflet").then((mod) => mod.Marker),
  { ssr: false }
)
const Popup = dynamic(
  () => import("react-leaflet").then((mod) => mod.Popup),
  { ssr: false }
)
const Polyline = dynamic(
  () => import("react-leaflet").then((mod) => mod.Polyline),
  { ssr: false }
)
const useMap = dynamic(
  () => import("react-leaflet").then((mod) => mod.useMap),
  { ssr: false }
) as unknown as () => import("leaflet").Map

// Types for DFS animation
type EdgeState = "unvisited" | "active" | "visited" | "return"
type NodeState = "unvisited" | "active" | "visited" | "stop-reached"
type ViewMode = "map" | "graph"

interface RouteMapProps {
  selectedStop: number | null
  onSelectStop: (id: number | null) => void
}

// SVG Graph Overlay Component
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
    const newPositions: Record<string, { x: number; y: number }> = {}
    graphNodes.forEach((node) => {
      const point = map.latLngToLayerPoint([node.lat, node.lng])
      newPositions[node.id] = { x: point.x, y: point.y }
    })
    setPositions(newPositions)
  }, [map])

  useEffect(() => {
    if (!map) return
    updatePositions()
    map.on("move", updatePositions)
    map.on("zoom", updatePositions)
    return () => {
      map.off("move", updatePositions)
      map.off("zoom", updatePositions)
    }
  }, [map, updatePositions])

  const getEdgeStyle = (state: EdgeState, isReturn: boolean) => {
    switch (state) {
      case "active":
        return { stroke: "var(--amber)", strokeWidth: 3, opacity: 1, dashArray: undefined }
      case "visited":
        return { stroke: "var(--red)", strokeWidth: 2.5, opacity: 0.85, dashArray: undefined }
      case "return":
        return { stroke: "var(--gray-mid)", strokeWidth: 1.5, opacity: 0.8, dashArray: "4 3" }
      default:
        return { stroke: "var(--gray-light)", strokeWidth: 1, opacity: 0.3, dashArray: isReturn ? "4 3" : undefined }
    }
  }

  const getNodeStyle = (node: GraphNode, state: NodeState) => {
    if (node.type === "warehouse") {
      return { r: 14, fill: "var(--amber)", stroke: "var(--amber)", strokeWidth: 2 }
    }
    switch (state) {
      case "active":
        return { r: 6, fill: "var(--amber)", stroke: "var(--amber)", strokeWidth: 0 }
      case "visited":
        return { r: 4, fill: "var(--red)", stroke: "none", strokeWidth: 0 }
      case "stop-reached":
        return { r: 14, fill: "var(--red)", stroke: "var(--red-dark)", strokeWidth: 2 }
      default:
        return { r: node.type === "stop" ? 8 : 3, fill: node.type === "stop" ? "var(--charcoal)" : "var(--gray-mid)", stroke: node.type === "stop" ? "var(--gray-mid)" : "none", strokeWidth: node.type === "stop" ? 2 : 0 }
    }
  }

  if (Object.keys(positions).length === 0) return null

  return (
    <svg
      className="pointer-events-none absolute inset-0 z-[500]"
      style={{ width: "100%", height: "100%" }}
    >
      <defs>
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Edges */}
      {graphEdges.map((edge) => {
        const fromPos = positions[edge.from]
        const toPos = positions[edge.to]
        if (!fromPos || !toPos) return null
        const key = getEdgeKey(edge.from, edge.to)
        const state = edgeStates[key] || "unvisited"
        const style = getEdgeStyle(state, !!edge.isReturn)
        return (
          <line
            key={key}
            x1={fromPos.x}
            y1={fromPos.y}
            x2={toPos.x}
            y2={toPos.y}
            stroke={style.stroke}
            strokeWidth={style.strokeWidth}
            opacity={style.opacity}
            strokeDasharray={style.dashArray}
            strokeLinecap="round"
            className={state === "active" ? "animate-pulse" : ""}
            filter={state === "active" ? "url(#glow)" : undefined}
          />
        )
      })}

      {/* Nodes */}
      {graphNodes.map((node) => {
        const pos = positions[node.id]
        if (!pos) return null
        const state = nodeStates[node.id] || "unvisited"
        const style = getNodeStyle(node, state)
        const isStopReached = state === "stop-reached" && node.type === "stop"
        const isWarehouse = node.type === "warehouse"

        return (
          <g key={node.id} className={state === "active" ? "animate-pulse" : ""}>
            <circle
              cx={pos.x}
              cy={pos.y}
              r={style.r}
              fill={style.fill}
              stroke={style.stroke}
              strokeWidth={style.strokeWidth}
              filter={state === "active" ? "url(#glow)" : undefined}
            />
            {(isStopReached || (node.type === "stop" && state === "unvisited")) && node.stopId && (
              <text
                x={pos.x}
                y={pos.y}
                textAnchor="middle"
                dominantBaseline="central"
                fill="white"
                fontSize={isStopReached ? 11 : 9}
                fontWeight="bold"
              >
                {node.stopId}
              </text>
            )}
            {isWarehouse && (
              <text
                x={pos.x}
                y={pos.y}
                textAnchor="middle"
                dominantBaseline="central"
                fill="#0B0F1C"
                fontSize={12}
                fontWeight="bold"
              >
                W
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

// Map event handler component
function MapEvents({ onMapReady }: { onMapReady: (map: import("leaflet").Map) => void }) {
  const MapHook = dynamic(
    () => import("react-leaflet").then((mod) => {
      const Component = () => {
        const map = mod.useMap()
        useEffect(() => {
          onMapReady(map)
        }, [map])
        return null
      }
      return Component
    }),
    { ssr: false }
  )
  return <MapHook />
}

export function RouteMap({ selectedStop, onSelectStop }: RouteMapProps) {
  const { t } = useLanguage()
  const [isMounted, setIsMounted] = useState(false)
  const [L, setL] = useState<typeof import("leaflet") | null>(null)
  const [mapInstance, setMapInstance] = useState<import("leaflet").Map | null>(null)

  // View mode toggle
  const [viewMode, setViewMode] = useState<ViewMode>("map")

  // DFS Animation state
  const [edgeStates, setEdgeStates] = useState<Record<string, EdgeState>>({})
  const [nodeStates, setNodeStates] = useState<Record<string, NodeState>>({})
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState(150)
  const [soundOn, setSoundOn] = useState(true)
  const audioContextRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    setIsMounted(true)
    import("leaflet").then((leaflet) => {
      setL(leaflet.default)
    })
    import("leaflet/dist/leaflet.css")
  }, [])

  // Audio functions
  const playAlgoBeep = useCallback((nodeIndex: number, totalNodes: number) => {
    if (!soundOn) return
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as typeof window & { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
    }
    const ctx = audioContextRef.current
    
    // Different sounds for intersections vs stops
    const isStop = nodeIndex > 0 && nodeIndex < totalNodes - 1 // Middle nodes are stops
    
    if (isStop) {
      // Stop ding: frequency 520Hz, duration 60ms, volume 0.18
      // + overtone 780Hz, duration 100ms
      const osc1 = ctx.createOscillator()
      const osc2 = ctx.createOscillator()
      const gain = ctx.createGain()
      
      osc1.connect(gain)
      osc2.connect(gain)
      gain.connect(ctx.destination)
      
      osc1.type = 'sine'
      osc1.frequency.value = 520
      
      osc2.type = 'sine'
      osc2.frequency.value = 780
      
      gain.gain.setValueAtTime(0, ctx.currentTime)
      gain.gain.linearRampToValueAtTime(0.18, ctx.currentTime + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1)
      
      osc1.start(ctx.currentTime)
      osc1.stop(ctx.currentTime + 0.06)
      osc2.start(ctx.currentTime)
      osc2.stop(ctx.currentTime + 0.1)
    } else {
      // Intersection tick: frequency 1200Hz, duration 20ms, volume 0.06
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      
      osc.connect(gain)
      gain.connect(ctx.destination)
      
      osc.type = 'sine'
      osc.frequency.value = 1200
      
      gain.gain.setValueAtTime(0, ctx.currentTime)
      gain.gain.linearRampToValueAtTime(0.06, ctx.currentTime + 0.005)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.02)
      
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.02)
    }
  }, [soundOn])

  const playCompletionChord = useCallback(() => {
    if (!soundOn) return
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as typeof window & { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
    }
    const ctx = audioContextRef.current
    const notes = [523, 659, 784, 1046] // C5, E5, G5, C6
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.type = 'sine'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0, ctx.currentTime + i * 0.08)
      gain.gain.linearRampToValueAtTime(0.12, ctx.currentTime + i * 0.08 + 0.01)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.08 + 0.2)
      osc.start(ctx.currentTime + i * 0.08)
      osc.stop(ctx.currentTime + i * 0.08 + 0.2)
    })
  }, [soundOn])

  const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

  const startAnimation = useCallback(async () => {
    setIsPlaying(true)
    setEdgeStates({})
    setNodeStates({ wh: "visited" })

    for (let i = 0; i < routePath.length - 1; i++) {
      const fromId = routePath[i]
      const toId = routePath[i + 1]
      const edgeKey = getEdgeKey(fromId, toId)
      const toNode = getNodeById(toId)

      // Activate edge
      setEdgeStates(prev => ({ ...prev, [edgeKey]: "active" }))
      setNodeStates(prev => ({ ...prev, [toId]: "active" }))

      // Play algorithm beep when edge STARTS drawing
      playAlgoBeep(i + 1, routePath.length)

      await sleep(100) // Edge animation time: 100ms per edge

      // Mark as visited
      const isReturn = graphEdges.find(e => e.from === fromId && e.to === toId)?.isReturn
      setEdgeStates(prev => ({
        ...prev,
        [edgeKey]: isReturn ? "return" : "visited"
      }))
      
      if (toNode?.type === "stop") {
        setNodeStates(prev => ({ ...prev, [toId]: "stop-reached" }))
      } else {
        setNodeStates(prev => ({ ...prev, [toId]: "visited" }))
      }
    }
    
    // Play completion chord when route finishes
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

  // Create custom icons
  const createStopIcon = (number: number, isSelected: boolean) => {
    return L.divIcon({
      className: "custom-marker",
      html: `
        <div style="
          width: 28px;
          height: 28px;
          background: ${isSelected ? "var(--amber)" : "var(--red)"};
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-weight: bold;
          font-size: 12px;
          border: 2px solid ${isSelected ? "var(--amber)" : "var(--red-dark)"};
          box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        ">${number}</div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    })
  }

  const warehouseIcon = L.divIcon({
    className: "custom-marker",
    html: `
      <div style="
        width: 32px;
        height: 32px;
        background: var(--amber);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--black);
        font-weight: bold;
        font-size: 14px;
        border: 2px solid var(--amber);
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
      ">W</div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  })

  // Create route coordinates
  const routeCoordinates: [number, number][] = [
    [routeData.warehouse.lat, routeData.warehouse.lng],
    ...routeData.stops.map((stop) => [stop.lat, stop.lng] as [number, number]),
  ]

  // Return line (dashed)
  const returnCoordinates: [number, number][] = [
    [routeData.stops[routeData.stops.length - 1].lat, routeData.stops[routeData.stops.length - 1].lng],
    [routeData.warehouse.lat, routeData.warehouse.lng],
  ]

  const center: [number, number] = [41.543, 2.222]

  return (
    <div className="relative h-full w-full">
      {/* View Toggle */}
      <div className="absolute left-1/2 top-3 z-[1000] flex -translate-x-1/2 overflow-hidden rounded-lg border border-border bg-card">
        <button
          onClick={() => setViewMode("map")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
            viewMode === "map"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Map className="h-4 w-4" />
          Mapa
        </button>
        <button
          onClick={() => setViewMode("graph")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
            viewMode === "graph"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <GitBranch className="h-4 w-4" />
          Graf DFS
        </button>
      </div>

      {/* DFS Controls */}
      {viewMode === "graph" && (
        <div className="absolute right-3 top-3 z-[1000] flex flex-col gap-2 rounded-lg border border-border bg-card/95 p-3 backdrop-blur-sm">
          {/* Play/Reset buttons */}
          <div className="flex gap-2">
            <button
              onClick={startAnimation}
              disabled={isPlaying}
              className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isPlaying
                  ? "cursor-not-allowed bg-muted text-muted-foreground"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              }`}
            >
              <Play className="h-4 w-4" />
              Iniciar ruta
            </button>
            <button
              onClick={resetAnimation}
              className="flex items-center justify-center rounded-lg border border-border px-3 py-2 text-muted-foreground transition-colors hover:border-muted-foreground hover:text-foreground"
            >
              <RotateCw className="h-4 w-4" />
            </button>
          </div>

          {/* Speed selector */}
          <div className="flex gap-1">
            <button
              onClick={() => setSpeed(300)}
              className={`flex-1 rounded px-2 py-1 text-xs font-medium transition-colors ${
                speed === 300
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              Lent
            </button>
            <button
              onClick={() => setSpeed(150)}
              className={`flex-1 rounded px-2 py-1 text-xs font-medium transition-colors ${
                speed === 150
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              Normal
            </button>
            <button
              onClick={() => setSpeed(50)}
              className={`flex-1 rounded px-2 py-1 text-xs font-medium transition-colors ${
                speed === 50
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              Rapid
            </button>
          </div>

          {/* Sound toggle */}
          <button
            onClick={() => setSoundOn(!soundOn)}
            className={`flex items-center justify-center gap-2 rounded-lg py-1.5 text-xs transition-colors ${
              soundOn
                ? "bg-muted text-foreground"
                : "border border-border text-muted-foreground"
            }`}
          >
            {soundOn ? <Volume2 className="h-3.5 w-3.5" /> : <VolumeX className="h-3.5 w-3.5" />}
            {soundOn ? "So activat" : "So desactivat"}
          </button>
        </div>
      )}

      <MapContainer
        center={center}
        zoom={13}
        style={{ height: "100%", width: "100%" }}
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        <MapEvents onMapReady={setMapInstance} />

        {/* Only show markers and route in map mode */}
        {viewMode === "map" && (
          <>
            {/* Warehouse marker */}
            <Marker
              position={[routeData.warehouse.lat, routeData.warehouse.lng]}
              icon={warehouseIcon}
            >
              <Popup>
                <div className="min-w-[180px]">
                  <p className="font-bold text-white">{t.dashboard.warehouse}</p>
                  <p className="text-[#5570A0]">Start / End</p>
                </div>
              </Popup>
            </Marker>

            {/* Stop markers */}
            {routeData.stops.map((stop) => (
              <Marker
                key={stop.id}
                position={[stop.lat, stop.lng]}
                icon={createStopIcon(stop.id, selectedStop === stop.id)}
                eventHandlers={{
                  click: () => onSelectStop(selectedStop === stop.id ? null : stop.id),
                }}
              >
                <Popup>
                  <StopPopup stop={stop} />
                </Popup>
              </Marker>
            ))}

            {/* Main route line */}
            <Polyline
              positions={routeCoordinates}
              color="var(--red)"
              weight={3}
              opacity={0.8}
            />

            {/* Return line (dashed) */}
            <Polyline
              positions={returnCoordinates}
              color="var(--amber)"
              weight={2}
              opacity={0.6}
              dashArray="10, 10"
            />
          </>
        )}
      </MapContainer>

      {/* Graph overlay (only in graph mode) */}
      {viewMode === "graph" && (
        <GraphOverlay
          map={mapInstance}
          edgeStates={edgeStates}
          nodeStates={nodeStates}
        />
      )}

      {/* KPI bar */}
      <div className="absolute bottom-4 left-1/2 z-[1000] flex -translate-x-1/2 gap-3">
        <KPICard icon={<Truck className="h-4 w-4" />} value={`${routeData.totalStops} ${t.dashboard.stops}`} />
        <KPICard icon={<Package className="h-4 w-4" />} value={`${routeData.totalReferences} ${t.dashboard.references}`} />
        <KPICard icon={<Clock className="h-4 w-4" />} value={routeData.estimatedTime} />
        <KPICard icon={<RotateCcw className="h-4 w-4" />} value={`${routeData.totalReturnables} ${t.dashboard.returnables}`} />
      </div>

      <style jsx global>{`
        /* Node animations removed for instant appearance */
      `}</style>
    </div>
  )
}

function StopPopup({ stop }: { stop: Stop }) {
  return (
    <div className="min-w-[200px]">
      <p className="font-bold text-foreground">{stop.name}</p>
      <p className="text-sm text-muted-foreground">{stop.address}</p>
      <div className="mt-2 border-t border-border pt-2">
        <p className="text-xs text-muted-foreground">
          {stop.products.references} refs · {stop.products.barrels} barrils · {stop.products.boxes} caixes
        </p>
        <p className="text-xs text-muted-foreground">{stop.timeWindow}</p>
        {stop.returnables && (
          <span className="mt-1 inline-block rounded-full bg-green-light px-2 py-0.5 text-[10px] text-green">
            {stop.returnables.count} {stop.returnables.type === "barrels" ? "barrils" : "caixes"}
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
