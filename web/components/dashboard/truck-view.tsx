"use client"

import { useRef, useState, useMemo, useEffect } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import { OrbitControls, Text, RoundedBox } from "@react-three/drei"
import { useLanguage } from "@/lib/i18n"
import { useTruckLoad, useDriverRoutes } from "@/hooks/use-truck-load"
import { useMongoDBTruck, type MongoDBTruckStats } from "@/hooks/use-mongodb-truck"
import type { TruckLoadData, DriverRoute } from "@/lib/types/truck-load"
import { getClientColor } from "@/lib/types/truck-load"
import * as THREE from "three"
import { Loader2, Truck, MapPin, Route, Package, Layers, Box, BarChart3 } from "lucide-react"

interface TruckViewProps {
  selectedStop: number | null
  onSelectStop: (id: number | null) => void
  routeId: string
  driverId?: string
}

// Generate stop info from client matrix
function generateStopsFromMatrix(clients: number[][][]): { stopId: number; stopName: string; color: string; cellCount: number }[] {
  const stopCounts: Record<number, number> = {}
  
  for (let x = 0; x < clients.length; x++) {
    for (let y = 0; y < clients[x].length; y++) {
      for (let z = 0; z < clients[x][y].length; z++) {
        const clientId = clients[x][y][z]
        if (clientId > 0) {
          stopCounts[clientId] = (stopCounts[clientId] || 0) + 1
        }
      }
    }
  }

  const stopNames = [
    "CASA MAURA",
    "BAR EL RACO",
    "REST. CAN PERE",
    "CAFE CENTRAL",
    "FORN DE PA",
    "MERCAT LOCAL",
    "HOTEL MARINA",
    "SUPERMERCAT",
    "PASTISSERIA",
    "CARNISSERIA"
  ]

  return Object.entries(stopCounts)
    .map(([id, count]) => ({
      stopId: Number(id),
      stopName: stopNames[Number(id) - 1] || `Client ${id}`,
      color: getClientColor(Number(id)),
      cellCount: count
    }))
    .sort((a, b) => a.stopId - b.stopId)
}

export function TruckView({ selectedStop, onSelectStop, routeId: initialRouteId, driverId = "DRV001" }: TruckViewProps) {
  const { t } = useLanguage()
  const [selectedRouteId, setSelectedRouteId] = useState(initialRouteId)
  const [hoveredStop, setHoveredStop] = useState<number | null>(null)
  const [hoveredCell, setHoveredCell] = useState<{ col: number; level: number; row: number } | null>(null)
  const [mongoStats, setMongoStats] = useState<MongoDBTruckStats | null>(null)

  // Obtener todas las rutas del conductor
  const { routes, isLoading: routesLoading } = useDriverRoutes(driverId)
  
  // Obtener datos de carga del camion seleccionado (mock API)
  const { truckLoad, isLoading: loadLoading, isError } = useTruckLoad(selectedRouteId)

  // Fetch real stats from MongoDB
  const { truckData: mongoData, isLoading: mongoLoading } = useMongoDBTruck()

  // Update stats when MongoDB data is available
  useEffect(() => {
    if (mongoData?.stats) {
      setMongoStats(mongoData.stats)
    }
  }, [mongoData])

  // Generate stops from the client matrix
  const stops = useMemo(() => {
    if (!truckLoad?.truck?.clients) return []
    return generateStopsFromMatrix(truckLoad.truck.clients)
  }, [truckLoad?.truck?.clients])

  const isLoading = routesLoading || loadLoading

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#0B0F1C]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-[#C8102E]" />
          <p className="text-sm text-[#5570A0]">Carregant dades...</p>
        </div>
      </div>
    )
  }

  if (isError || !truckLoad || !truckLoad.truck) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#0B0F1C]">
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6 text-center">
          <p className="text-sm text-red-400">Error carregant les dades</p>
        </div>
      </div>
    )
  }

  const { truck, capacity } = truckLoad
  const { dimensions: matrixConfig, physicalSize: dimensions, clients, occupancy } = truck

  const occupationPercentage = Math.round(
    (capacity.usedCells / capacity.totalCells) * 100
  )

  // Info de la celda hover
  const hoveredCellInfo = hoveredCell
    ? {
        value: occupancy[hoveredCell.col]?.[hoveredCell.level]?.[hoveredCell.row] ?? 0,
        clientId: clients[hoveredCell.col]?.[hoveredCell.level]?.[hoveredCell.row] ?? 0,
        color: getClientColor(clients[hoveredCell.col]?.[hoveredCell.level]?.[hoveredCell.row] ?? 0),
        stopName: stops.find(s => s.stopId === clients[hoveredCell.col]?.[hoveredCell.level]?.[hoveredCell.row])?.stopName || "Buit"
      }
    : null

  return (
    <div className="flex h-full w-full">
      {/* Panel izquierdo - Lista de rutas */}
      <div className="flex w-[200px] flex-col border-r border-[#1E2A45] bg-[#0A0E1A]">
        <div className="border-b border-[#1E2A45] p-3">
          <h3 className="flex items-center gap-2 text-xs font-medium text-[#5570A0]">
            <Route className="h-3.5 w-3.5" />
            RUTES ASSIGNADES
          </h3>
        </div>
        
        <div className="flex-1 overflow-y-auto p-2">
          {routes.map((route) => (
            <RouteCard
              key={route.routeId}
              route={route}
              isSelected={route.routeId === selectedRouteId}
              onSelect={() => setSelectedRouteId(route.routeId)}
            />
          ))}
        </div>
      </div>

      {/* Main content area */}
      <div className="relative flex flex-1 flex-col">
        {/* KPI Bar - Real data from MongoDB */}
        <div className="flex items-center justify-between border-b border-[#1E2A45] bg-[#0A0E1A] px-4 py-3">
          <div className="flex items-center gap-6">
            {/* Parades */}
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#C8102E]/10">
                <MapPin className="h-4 w-4 text-[#C8102E]" />
              </div>
              <div>
                <p className="text-[10px] text-[#5570A0]">Parades</p>
                <p className="text-sm font-semibold text-white">
                  {mongoStats?.n_paradas ?? stops.length}
                </p>
              </div>
            </div>

            {/* Caixes */}
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#F5A623]/10">
                <Box className="h-4 w-4 text-[#F5A623]" />
              </div>
              <div>
                <p className="text-[10px] text-[#5570A0]">Caixes</p>
                <p className="text-sm font-semibold text-white">
                  {mongoStats?.total_cajas ?? capacity.usedCells}
                </p>
              </div>
            </div>

            {/* Palets */}
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#22C55E]/10">
                <Layers className="h-4 w-4 text-[#22C55E]" />
              </div>
              <div>
                <p className="text-[10px] text-[#5570A0]">Palets</p>
                <p className="text-sm font-semibold text-white">
                  {mongoStats?.n_palets_usados ?? 0}
                </p>
              </div>
            </div>

            {/* Ocupacio */}
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#3B82F6]/10">
                <BarChart3 className="h-4 w-4 text-[#3B82F6]" />
              </div>
              <div>
                <p className="text-[10px] text-[#5570A0]">Ocupacio</p>
                <p className="text-sm font-semibold text-white">
                  {mongoStats?.ocupacion_pct?.toFixed(1) ?? occupationPercentage}%
                </p>
              </div>
            </div>
          </div>

          {/* MongoDB status indicator */}
          <div className="flex items-center gap-2">
            {mongoLoading ? (
              <div className="flex items-center gap-2 text-[10px] text-[#5570A0]">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Connectant MongoDB...</span>
              </div>
            ) : mongoStats ? (
              <div className="flex items-center gap-2 text-[10px] text-[#22C55E]">
                <div className="h-2 w-2 rounded-full bg-[#22C55E]" />
                <span>MongoDB Atlas</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-[10px] text-[#F5A623]">
                <div className="h-2 w-2 rounded-full bg-[#F5A623]" />
                <span>Dades locals</span>
              </div>
            )}
          </div>
        </div>

        {/* Canvas 3D */}
        <div className="relative flex-1">
          <Canvas
          camera={{ position: [12, 8, 12], fov: 45 }}
          style={{ background: "#0B0F1C" }}
        >
          <ambientLight intensity={0.4} />
          <directionalLight position={[10, 15, 10]} intensity={0.7} />
          <pointLight position={[-10, 10, -10]} intensity={0.2} />

          <TruckContainer
            matrixConfig={matrixConfig}
            dimensions={dimensions}
            occupancy={occupancy}
            clients={clients}
            stops={stops}
            selectedStop={selectedStop}
            hoveredStop={hoveredStop}
            setHoveredStop={setHoveredStop}
            hoveredCell={hoveredCell}
            setHoveredCell={setHoveredCell}
            onSelectStop={onSelectStop}
          />

          <OrbitControls
            enablePan={true}
            enableZoom={true}
            enableRotate={true}
            minDistance={5}
            maxDistance={30}
            target={[0, 0, 0]}
          />

          <gridHelper args={[20, 20, "#1E2A45", "#1E2A45"]} position={[0, -2.5, 0]} />
        </Canvas>

        {/* Tooltip de celda */}
        {hoveredCellInfo && hoveredCellInfo.value === 1 && (
          <div className="pointer-events-none absolute left-4 top-4 rounded-lg border border-[#1E2A45] bg-[#10162A]/95 p-3 backdrop-blur-sm">
            <div className="flex items-center gap-2">
              <div
                className="h-3 w-3 rounded"
                style={{ backgroundColor: hoveredCellInfo.color }}
              />
              <p className="text-sm font-medium text-white">{hoveredCellInfo.stopName}</p>
            </div>
            <p className="mt-1 text-xs text-[#5570A0]">
              Client {hoveredCellInfo.clientId}
            </p>
            {hoveredCell && (
              <p className="text-xs text-[#5570A0]">
                Pos: [{hoveredCell.col}, {hoveredCell.level}, {hoveredCell.row}]
              </p>
            )}
          </div>
        )}

        {/* Info del camion */}
        <div className="absolute bottom-16 left-4 rounded-lg border border-[#1E2A45] bg-[#10162A]/90 px-3 py-2 text-xs backdrop-blur-sm">
          <p className="font-medium text-white">{truckLoad.truckPlate}</p>
          <p className="text-[#5570A0]">{dimensions.length}m x {dimensions.width}m x {dimensions.height}m</p>
        </div>

        {/* Info de la matriz */}
        <div className="absolute bottom-16 right-4 rounded-lg border border-[#1E2A45] bg-[#10162A]/90 px-3 py-2 text-xs backdrop-blur-sm">
          <p className="text-[#F5A623]">
            Matriu: {matrixConfig.x} x {matrixConfig.y} x {matrixConfig.z}
          </p>
          <p className="text-[#5570A0]">
            {capacity.usedCells} / {capacity.totalCells} cel·les
          </p>
        </div>

        {/* Controles */}
        <div className="absolute bottom-4 left-4 rounded-lg border border-[#1E2A45] bg-[#10162A]/90 px-3 py-2 text-xs text-[#5570A0] backdrop-blur-sm">
          {t.dashboard.dragToRotate} - {t.dashboard.scrollToZoom}
        </div>
      </div>
      </div>

      {/* Panel derecho - Leyenda */}
      <div className="flex w-[220px] flex-col border-l border-[#1E2A45] bg-[#10162A] overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4">
          <h3 className="mb-4 text-xs font-medium text-white">{t.dashboard.legend}</h3>

          {/* Paradas por color */}
          <div className="space-y-2">
            {stops.map((stop) => (
              <button
                key={stop.stopId}
                onClick={() => onSelectStop(selectedStop === stop.stopId ? null : stop.stopId)}
                onMouseEnter={() => setHoveredStop(stop.stopId)}
                onMouseLeave={() => setHoveredStop(null)}
                className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition-colors ${
                  selectedStop === stop.stopId
                    ? "bg-white/10 ring-1 ring-white/20"
                    : "hover:bg-[#151D35]"
                }`}
              >
                <div
                  className="h-4 w-4 rounded"
                  style={{ backgroundColor: stop.color }}
                />
                <div className="flex-1 min-w-0">
                  <p className="truncate text-xs text-white">{stop.stopId}. {stop.stopName}</p>
                  <p className="text-[9px] text-[#5570A0]">{stop.cellCount} blocs</p>
                </div>
              </button>
            ))}
          </div>

          <div className="my-4 h-px bg-[#1E2A45]" />

          {/* Ocupacion */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-[#5570A0]">{t.dashboard.occupation}</span>
              <span className="text-sm font-medium text-white">{occupationPercentage}%</span>
            </div>
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-[#1E2A45]">
              <div
                className="h-full rounded-full bg-gradient-to-r from-[#C8102E] to-[#F5A623] transition-all"
                style={{ width: `${occupationPercentage}%` }}
              />
            </div>
          </div>

          {/* Peso */}
          <div className="mt-4 space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-[#5570A0]">Pes:</span>
              <span className="text-white">{capacity.usedWeight} kg</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#5570A0]">Max:</span>
              <span className="text-[#5570A0]">{capacity.totalWeight} kg</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-[#1E2A45] p-3">
          <p className="text-[9px] text-[#5570A0]">
            Ruta: {selectedRouteId}
          </p>
        </div>
      </div>
    </div>
  )
}

// Componente de tarjeta de ruta
function RouteCard({ route, isSelected, onSelect }: { route: DriverRoute; isSelected: boolean; onSelect: () => void }) {
  const statusColors = {
    pending: "bg-yellow-500/20 text-yellow-400",
    in_progress: "bg-blue-500/20 text-blue-400",
    completed: "bg-green-500/20 text-green-400",
  }

  const statusLabels = {
    pending: "Pendent",
    in_progress: "En curs",
    completed: "Completat",
  }

  return (
    <button
      onClick={onSelect}
      className={`mb-2 w-full rounded-lg border p-3 text-left transition-all ${
        isSelected
          ? "border-[#C8102E] bg-[#C8102E]/10"
          : "border-[#1E2A45] bg-[#10162A] hover:border-[#2A3A5A]"
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Truck className={`h-4 w-4 ${isSelected ? "text-[#C8102E]" : "text-[#5570A0]"}`} />
          <span className="text-xs font-medium text-white">{route.routeId}</span>
        </div>
        <span className={`rounded px-1.5 py-0.5 text-[9px] ${statusColors[route.status]}`}>
          {statusLabels[route.status]}
        </span>
      </div>
      
      <div className="mt-2 space-y-1">
        <p className="text-[10px] text-[#5570A0]">
          <span className="text-[#7A90C0]">{route.truckPlate}</span>
        </p>
        <div className="flex items-center gap-2 text-[10px] text-[#5570A0]">
          <MapPin className="h-3 w-3" />
          <span>{route.stopCount} parades</span>
          <span>·</span>
          <span>{route.estimatedKm} km</span>
        </div>
        <p className="text-[9px] text-[#5570A0]">
          Matriu: {route.matrixConfig.cols}x{route.matrixConfig.levels}x{route.matrixConfig.rows}
        </p>
      </div>
    </button>
  )
}

// Componente 3D del contenedor del camion
interface TruckContainerProps {
  matrixConfig: { x: number; y: number; z: number }
  dimensions: { length: number; width: number; height: number }
  occupancy: number[][][]
  clients: number[][][]
  stops: { stopId: number; stopName: string; color: string; cellCount: number }[]
  selectedStop: number | null
  hoveredStop: number | null
  setHoveredStop: (stop: number | null) => void
  hoveredCell: { col: number; level: number; row: number } | null
  setHoveredCell: (cell: { col: number; level: number; row: number } | null) => void
  onSelectStop: (id: number | null) => void
}

function TruckContainer({
  matrixConfig,
  dimensions,
  occupancy,
  clients,
  stops,
  selectedStop,
  hoveredStop,
  setHoveredStop,
  hoveredCell,
  setHoveredCell,
  onSelectStop,
}: TruckContainerProps) {
  const groupRef = useRef<THREE.Group>(null)

  // Rotacion suave
  useFrame((state) => {
    if (groupRef.current && !selectedStop && !hoveredStop) {
      groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.1) * 0.03
    }
  })

  const { x: cols, y: levels, z: rows } = matrixConfig

  // Calcular tamano de cada celda basado en dimensiones fisicas
  const cellWidth = dimensions.length / cols
  const cellHeight = dimensions.height / levels
  const cellDepth = dimensions.width / rows

  // Offset para centrar
  const offsetX = -dimensions.length / 2
  const offsetY = -1.5
  const offsetZ = -dimensions.width / 2

  // Gap entre bloques
  const gap = 0.03

  return (
    <group ref={groupRef}>
      {/* Suelo del camion */}
      <RoundedBox
        args={[dimensions.length + 0.2, 0.12, dimensions.width + 0.2]}
        radius={0.03}
        position={[0, offsetY - 0.06, 0]}
      >
        <meshStandardMaterial color="#1A2340" />
      </RoundedBox>

      {/* Paredes transparentes */}
      {/* Izquierda */}
      <RoundedBox
        args={[dimensions.length + 0.2, dimensions.height + 0.3, 0.06]}
        radius={0.02}
        position={[0, offsetY + dimensions.height / 2 + 0.1, -dimensions.width / 2 - 0.08]}
      >
        <meshStandardMaterial color="#1E2A45" transparent opacity={0.12} />
      </RoundedBox>

      {/* Derecha */}
      <RoundedBox
        args={[dimensions.length + 0.2, dimensions.height + 0.3, 0.06]}
        radius={0.02}
        position={[0, offsetY + dimensions.height / 2 + 0.1, dimensions.width / 2 + 0.08]}
      >
        <meshStandardMaterial color="#1E2A45" transparent opacity={0.12} />
      </RoundedBox>

      {/* Fondo (cabina) */}
      <RoundedBox
        args={[0.06, dimensions.height + 0.3, dimensions.width + 0.2]}
        radius={0.02}
        position={[offsetX - 0.08, offsetY + dimensions.height / 2 + 0.1, 0]}
      >
        <meshStandardMaterial color="#1E2A45" transparent opacity={0.12} />
      </RoundedBox>

      {/* Etiquetas */}
      <Text
        position={[offsetX - 0.2, offsetY + dimensions.height + 0.2, 0]}
        rotation={[0, Math.PI / 2, 0]}
        fontSize={0.2}
        color="#5570A0"
      >
        CABINA
      </Text>

      <Text
        position={[-offsetX + 0.2, offsetY + dimensions.height + 0.2, 0]}
        rotation={[0, -Math.PI / 2, 0]}
        fontSize={0.2}
        color="#5570A0"
      >
        PORTA
      </Text>

      {/* Renderizar todos los bloques de la matriz */}
      {occupancy.map((colData, col) =>
        colData.map((levelData, level) =>
          levelData.map((cellValue, row) => {
            if (cellValue === 0) return null

            const clientId = clients[col]?.[level]?.[row] ?? 0
            const color = getClientColor(clientId)

            const xPos = offsetX + col * cellWidth + cellWidth / 2
            const yPos = offsetY + level * cellHeight + cellHeight / 2
            const zPos = offsetZ + row * cellDepth + cellDepth / 2

            const isStopSelected = selectedStop === clientId
            const isStopHovered = hoveredStop === clientId
            const isCellHovered = hoveredCell?.col === col && hoveredCell?.level === level && hoveredCell?.row === row
            const showHighlight = isStopSelected || isStopHovered || isCellHovered

            return (
              <group
                key={`${col}-${level}-${row}`}
                position={[xPos, yPos, zPos]}
                onPointerEnter={(e) => {
                  e.stopPropagation()
                  setHoveredCell({ col, level, row })
                  if (clientId) setHoveredStop(clientId)
                }}
                onPointerLeave={(e) => {
                  e.stopPropagation()
                  setHoveredCell(null)
                  setHoveredStop(null)
                }}
                onClick={(e) => {
                  e.stopPropagation()
                  if (clientId) {
                    onSelectStop(selectedStop === clientId ? null : clientId)
                  }
                }}
              >
                <RoundedBox
                  args={[cellWidth - gap, cellHeight - gap, cellDepth - gap]}
                  radius={0.02}
                >
                  <meshStandardMaterial
                    color={color}
                    emissive={showHighlight ? color : "#000000"}
                    emissiveIntensity={showHighlight ? 0.4 : 0}
                  />
                </RoundedBox>

                {/* Borde si esta seleccionado */}
                {showHighlight && (
                  <lineSegments>
                    <edgesGeometry
                      args={[new THREE.BoxGeometry(cellWidth - gap + 0.02, cellHeight - gap + 0.02, cellDepth - gap + 0.02)]}
                    />
                    <lineBasicMaterial color="#FFFFFF" linewidth={2} />
                  </lineSegments>
                )}
              </group>
            )
          })
        )
      )}
    </group>
  )
}
