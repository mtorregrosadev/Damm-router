import useSWR from "swr"
import type { TruckLoadAPIResponse, TruckLoadData, DriverRoutesResponse, DriverRoute } from "@/lib/types/truck-load"

// =================================================================
// HOOK: useTruckLoad
// Fetches truck load data from the API using SWR for caching
// 
// CONEXION FUTURA A VULTR:
// El fetcher actual llama a /api/truck-load que tiene datos hardcodeados.
// Cuando conectes Vultr, solo necesitas modificar el API route,
// este hook seguira funcionando igual.
// =================================================================

const truckLoadFetcher = async (url: string): Promise<TruckLoadData | null> => {
  const response = await fetch(url)
  const json: TruckLoadAPIResponse = await response.json()
  
  if (!json.success) {
    throw new Error(json.error || "Failed to fetch truck load data")
  }
  
  return json.data
}

export function useTruckLoad(routeId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<TruckLoadData | null>(
    routeId ? `/api/truck-load?routeId=${routeId}` : null,
    truckLoadFetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      refreshInterval: 30000,
    }
  )

  return {
    truckLoad: data,
    isLoading,
    isError: error,
    refresh: mutate,
  }
}

// =================================================================
// HOOK: useDriverRoutes
// Fetches all routes for a specific driver
// Un conductor puede tener multiples rutas/camiones
// =================================================================

const driverRoutesFetcher = async (url: string): Promise<{ driverId: string; driverName: string; routes: DriverRoute[] } | null> => {
  const response = await fetch(url)
  const json: DriverRoutesResponse = await response.json()
  
  if (!json.success) {
    throw new Error(json.error || "Failed to fetch driver routes")
  }
  
  return {
    driverId: json.driverId,
    driverName: json.driverName,
    routes: json.routes,
  }
}

export function useDriverRoutes(driverId: string | null) {
  const { data, error, isLoading, mutate } = useSWR(
    driverId ? `/api/driver-routes?driverId=${driverId}` : null,
    driverRoutesFetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
    }
  )

  return {
    driverId: data?.driverId,
    driverName: data?.driverName,
    routes: data?.routes || [],
    isLoading,
    isError: error,
    refresh: mutate,
  }
}
