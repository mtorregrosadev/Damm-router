import { NextResponse } from "next/server"
import type { DriverRoutesResponse, DriverRoute } from "@/lib/types/truck-load"

// =================================================================
// API ROUTE: GET /api/driver-routes?driverId=DRV001
// 
// Devuelve todas las rutas asignadas a un conductor
// Cada ruta tiene su propio camion con dimensiones diferentes
// =================================================================

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const driverId = searchParams.get("driverId")

  if (!driverId) {
    return NextResponse.json<DriverRoutesResponse>({
      success: false,
      driverId: "",
      driverName: "",
      routes: [],
      error: "driverId is required",
    }, { status: 400 })
  }

  try {
    // =====================================================
    // TODO: Reemplazar con query real a Vultr DB
    // =====================================================

    const data = getMockDriverRoutes(driverId)

    if (!data) {
      return NextResponse.json<DriverRoutesResponse>({
        success: false,
        driverId,
        driverName: "",
        routes: [],
        error: `No routes found for driver ${driverId}`,
      }, { status: 404 })
    }

    return NextResponse.json<DriverRoutesResponse>({
      success: true,
      ...data,
    })
  } catch (error) {
    console.error("[API] Error fetching driver routes:", error)
    return NextResponse.json<DriverRoutesResponse>({
      success: false,
      driverId,
      driverName: "",
      routes: [],
      error: "Internal server error",
    }, { status: 500 })
  }
}

// =================================================================
// DATOS HARDCODEADOS - 3 rutas con diferentes camiones
// =================================================================
function getMockDriverRoutes(driverId: string): { driverId: string; driverName: string; routes: DriverRoute[] } | null {
  if (driverId !== "DRV001") {
    return null
  }

  // Jose Velez tiene 3 rutas asignadas con camiones diferentes
  return {
    driverId: "DRV001",
    driverName: "Jose Velez",
    routes: [
      {
        routeId: "DR0006",
        date: "2026-01-30",
        status: "in_progress",
        truckPlate: "4521-GKL",
        truckId: "TRK-0006",
        stopCount: 7,
        estimatedKm: 42,
        matrixConfig: { cols: 8, levels: 3, rows: 4 },
        dimensions: { length: 7.0, height: 2.4, width: 2.2 },
      },
      {
        routeId: "DR0012",
        date: "2026-01-30",
        status: "pending",
        truckPlate: "7834-BNM",
        truckId: "TRK-0012",
        stopCount: 5,
        estimatedKm: 28,
        matrixConfig: { cols: 6, levels: 2, rows: 3 },
        dimensions: { length: 5.0, height: 2.0, width: 1.8 },
      },
      {
        routeId: "DR0023",
        date: "2026-01-30",
        status: "pending",
        truckPlate: "2156-XYZ",
        truckId: "TRK-0023",
        stopCount: 4,
        estimatedKm: 35,
        matrixConfig: { cols: 10, levels: 4, rows: 5 },
        dimensions: { length: 9.0, height: 2.8, width: 2.4 },
      },
    ],
  }
}
