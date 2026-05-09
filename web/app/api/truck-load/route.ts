import { NextResponse } from "next/server"
import type { TruckLoadAPIResponse, TruckLoadData } from "@/web/lib/types/truck-load"

// =================================================================
// API ROUTE: GET /api/truck-load?routeId=DR0006
// 
// CONEXION FUTURA A VULTR:
// - Host: [TU_IP_VULTR]:3306
// - Database: ddi_smart_truck
// - El backend devolvera las dos matrices directamente como JSON
//
// ESTRUCTURA DE DOS MATRICES:
// - occupancy[x][y][z] = 0 (vacio) o 1 (lleno)
// - clients[x][y][z] = 0 (vacio) o 1..N (cliente ID)
// =================================================================

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const routeId = searchParams.get("routeId")

  if (!routeId) {
    return NextResponse.json<TruckLoadAPIResponse>({
      success: false,
      data: null,
      error: "routeId is required",
    }, { status: 400 })
  }

  try {
    // =====================================================
    // TODO: Reemplazar con query real a Vultr DB
    // 
    // const response = await fetch(`${VULTR_API}/truck-load/${routeId}`)
    // const data = await response.json()
    // =====================================================

    const data = getMockTruckLoad(routeId)

    if (!data) {
      return NextResponse.json<TruckLoadAPIResponse>({
        success: false,
        data: null,
        error: `No load data found for route ${routeId}`,
      }, { status: 404 })
    }

    return NextResponse.json<TruckLoadAPIResponse>({
      success: true,
      data,
    })
  } catch (error) {
    console.error("[API] Error fetching truck load:", error)
    return NextResponse.json<TruckLoadAPIResponse>({
      success: false,
      data: null,
      error: "Internal server error",
    }, { status: 500 })
  }
}

// =================================================================
// MOCK DATA - Datos hardcodeados hasta conectar con Vultr
// =================================================================

// Configuracion de camiones por ruta
const TRUCK_CONFIG: Record<string, {
  truckPlate: string
  matrixSize: { x: number; y: number; z: number }
  physicalSize: { length: number; width: number; height: number }
}> = {
  "DR0006": {
    truckPlate: "4521-GKL",
    matrixSize: { x: 4, y: 3, z: 3 },
    physicalSize: { length: 7.0, width: 2.2, height: 2.4 },
  },
  "DR0012": {
    truckPlate: "7834-BNM",
    matrixSize: { x: 5, y: 3, z: 4 },
    physicalSize: { length: 5.5, width: 2.0, height: 2.2 },
  },
  "DR0023": {
    truckPlate: "2156-XYZ",
    matrixSize: { x: 6, y: 4, z: 4 },
    physicalSize: { length: 9.0, width: 2.4, height: 2.8 },
  },
}

// MOCK MATRICES - Formato del documento
// occupancy: 0 = vacio, 1 = lleno
// clients: 0 = vacio, 1..N = cliente ID

const MOCK_MATRICES: Record<string, { occupancy: number[][][]; clients: number[][][] }> = {
  "DR0006": {
    // X=4 columnas, Y=3 alturas, Z=3 profundidad
    // Desde puerta (x=3) hacia cabina (x=0)
    occupancy: [
      // x=0 (cabina - primera parada, se descarga al final)
      [
        [1, 1, 0], // y=0 (suelo)
        [1, 0, 0], // y=1
        [0, 0, 0], // y=2 (arriba)
      ],
      // x=1
      [
        [1, 1, 1],
        [1, 1, 0],
        [1, 0, 0],
      ],
      // x=2
      [
        [1, 1, 1],
        [1, 1, 0],
        [0, 0, 0],
      ],
      // x=3 (puerta - ultima parada, se descarga primero)
      [
        [1, 1, 0],
        [1, 0, 0],
        [0, 0, 0],
      ],
    ],
    clients: [
      // x=0 - Cliente 1 (CASA MAURA - primera parada)
      [
        [1, 1, 0],
        [1, 0, 0],
        [0, 0, 0],
      ],
      // x=1 - Clientes 2 y 3
      [
        [2, 2, 3],
        [2, 3, 0],
        [3, 0, 0],
      ],
      // x=2 - Clientes 4 y 5
      [
        [4, 4, 5],
        [4, 5, 0],
        [0, 0, 0],
      ],
      // x=3 - Clientes 6 y 7 (ultimas paradas, cerca de la puerta)
      [
        [6, 7, 0],
        [6, 0, 0],
        [0, 0, 0],
      ],
    ],
  },
  "DR0012": {
    // X=5, Y=3, Z=4
    occupancy: [
      [[1, 1, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0]],
      [[1, 1, 1, 1], [1, 1, 1, 0], [1, 0, 0, 0]],
      [[1, 1, 1, 1], [1, 1, 0, 0], [0, 0, 0, 0]],
      [[1, 1, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0]],
      [[1, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0]],
    ],
    clients: [
      [[1, 1, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0]],
      [[1, 2, 2, 2], [2, 2, 2, 0], [2, 0, 0, 0]],
      [[3, 3, 3, 3], [3, 3, 0, 0], [0, 0, 0, 0]],
      [[4, 4, 4, 0], [4, 4, 0, 0], [0, 0, 0, 0]],
      [[5, 5, 0, 0], [5, 0, 0, 0], [0, 0, 0, 0]],
    ],
  },
  "DR0023": {
    // X=6, Y=4, Z=4 - Camion grande
    occupancy: [
      [[1, 1, 1, 1], [1, 1, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0]],
      [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 0], [1, 0, 0, 0]],
      [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 0, 0], [0, 0, 0, 0]],
      [[1, 1, 1, 1], [1, 1, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0]],
      [[1, 1, 1, 0], [1, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0]],
      [[1, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
    ],
    clients: [
      [[1, 1, 1, 1], [1, 1, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0]],
      [[1, 1, 2, 2], [1, 2, 2, 2], [2, 2, 2, 0], [2, 0, 0, 0]],
      [[2, 2, 2, 3], [2, 3, 3, 3], [3, 3, 0, 0], [0, 0, 0, 0]],
      [[3, 3, 3, 3], [3, 3, 3, 0], [3, 4, 0, 0], [0, 0, 0, 0]],
      [[4, 4, 4, 0], [4, 4, 0, 0], [4, 0, 0, 0], [0, 0, 0, 0]],
      [[4, 4, 0, 0], [4, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
    ],
  },
}

// Generar datos mock para una ruta
function getMockTruckLoad(routeId: string): TruckLoadData | null {
  const config = TRUCK_CONFIG[routeId]
  const matrices = MOCK_MATRICES[routeId]
  
  if (!config || !matrices) {
    return null
  }

  const { matrixSize, physicalSize, truckPlate } = config
  const { occupancy, clients } = matrices

  // Calcular ocupacion
  let totalCells = 0
  let usedCells = 0

  for (let x = 0; x < matrixSize.x; x++) {
    for (let y = 0; y < matrixSize.y; y++) {
      for (let z = 0; z < matrixSize.z; z++) {
        totalCells++
        if (occupancy[x][y][z] === 1) {
          usedCells++
        }
      }
    }
  }

  return {
    routeId,
    truckId: `TRK-${routeId.slice(2)}`,
    truckPlate,
    loadTimestamp: new Date().toISOString(),
    truck: {
      dimensions: matrixSize,
      physicalSize,
      occupancy,
      clients,
    },
    capacity: {
      totalCells,
      usedCells,
      totalWeight: Math.round(totalCells * 35),
      usedWeight: Math.round(usedCells * 35),
    },
  }
}
