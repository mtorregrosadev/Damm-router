import useSWR from "swr"

// =================================================================
// HOOK: useMongoDBTruck
// Fetches truck data from MongoDB via /api/truck-data
// 
// The API connects to MongoDB Atlas collection "resultados"
// and returns the 3D matrices for truck visualization
// =================================================================

export interface MongoDBTruckStats {
  n_paradas: number
  n_palets_usados: number
  total_cajas: number
  ocupacion_pct: number
}

export interface MongoDBTruckData {
  id: string
  occupancy: number[][][]
  clients: number[][][]
  paletsOccupancy: number[][][]
  paletsClients: number[][][]
  stats: MongoDBTruckStats
  dimensions: {
    x: number
    y: number
    z: number
  }
}

interface TruckDataResponse {
  success: boolean
  data: MongoDBTruckData | null
  error?: string
}

const fetcher = async (url: string): Promise<MongoDBTruckData | null> => {
  const response = await fetch(url)
  const json: TruckDataResponse = await response.json()

  if (!json.success) {
    throw new Error(json.error || "Failed to fetch truck data from MongoDB")
  }

  return json.data
}

export function useMongoDBTruck(rutaId?: string) {
  const url = rutaId ? `/api/truck-data?ruta=${encodeURIComponent(rutaId)}` : "/api/truck-data"

  const { data, error, isLoading, mutate } = useSWR<MongoDBTruckData | null>(
    url,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      refreshInterval: 30000, // Refresh every 30 seconds
    }
  )

  return {
    truckData: data,
    stats: data?.stats ?? null,
    isLoading,
    isError: error,
    refresh: mutate,
  }
}
