// =================================================================
// TIPOS PARA LA CARGA DEL CAMION - DOS MATRICES SEPARADAS
// Matrix1: Ocupacion (0/1)
// Matrix2: Cliente ID (0..N)
// =================================================================

// Datos de carga de un camion
export interface TruckData {
  dimensions: { x: number; y: number; z: number } // Tamano de la matriz
  physicalSize: { length: number; width: number; height: number } // Metros
  occupancy: number[][][] // Matrix1: 0 = vacio, 1 = lleno
  clients: number[][][] // Matrix2: 0 = vacio, 1..N = cliente ID
}

// Respuesta completa de la API de carga
export interface TruckLoadData {
  routeId: string
  truckId: string
  truckPlate: string
  loadTimestamp: string
  truck: TruckData
  // Info calculada
  capacity: {
    totalCells: number
    usedCells: number
    totalWeight: number
    usedWeight: number
  }
}

export interface TruckLoadAPIResponse {
  success: boolean
  data: TruckLoadData | null
  error?: string
}

// =================================================================
// TIPOS PARA RUTAS DEL CONDUCTOR
// =================================================================

export interface DriverRoute {
  routeId: string
  date: string
  status: "pending" | "in_progress" | "completed"
  truckPlate: string
  truckId: string
  stopCount: number
  estimatedKm: number
  matrixConfig: { cols: number; levels: number; rows: number }
  dimensions: { length: number; height: number; width: number }
}

export interface DriverRoutesResponse {
  success: boolean
  driverId: string
  driverName: string
  routes: DriverRoute[]
  error?: string
}

// =================================================================
// TIPOS PARA RUTAS Y MAPA
// =================================================================

export interface RouteStop {
  id: number
  name: string
  address: string
  lat: number
  lng: number
  timeWindow: string
  returnables?: number
}

export interface RouteData {
  stops: RouteStop[]
  warehouseStart: { lat: number; lng: number }
  warehouseEnd: { lat: number; lng: number }
  estimatedTime: string
  estimatedKm: number
  // Waypoints intermedios para curvas (opcional, del backend)
  waypoints?: { from: number; to: number; points: [number, number][] }[]
}

// =================================================================
// PALETA DE COLORES PARA CLIENTES
// =================================================================

export const CLIENT_COLORS: Record<number, string> = {
  1: "#E53935", // Rojo
  2: "#F5A623", // Dorado
  3: "#43A047", // Verde
  4: "#1E88E5", // Azul
  5: "#8E24AA", // Purpura
  6: "#00ACC1", // Cyan
  7: "#FB8C00", // Naranja
  8: "#D81B60", // Rosa
  9: "#5E35B1", // Violeta
  10: "#00897B", // Teal
}

export function getClientColor(clientId: number): string {
  if (clientId === 0) return "transparent"
  // Ciclar colores si hay mas de 10 clientes
  const colorIndex = ((clientId - 1) % 10) + 1
  return CLIENT_COLORS[colorIndex] || "#666666"
}
