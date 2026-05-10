import useSWR from "swr"
import type { RouteDataResponse, RouteStop, RouteSummary } from "@/lib/types/route-data"

const fetcher = async (url: string): Promise<RouteDataResponse> => {
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch route data")
  return res.json()
}

export function useRouteData(ruta?: string, data?: string) {
  const params = ruta && data
    ? `?ruta=${encodeURIComponent(ruta)}&data=${encodeURIComponent(data)}`
    : ''

  const { data: response, error, isLoading, mutate } = useSWR<RouteDataResponse>(
    `/api/route-data${params}`,
    fetcher,
    { revalidateOnFocus: false, refreshInterval: 60000 }
  )

  return {
    summary: response?.summary ?? null as RouteSummary | null,
    stops:   response?.stops   ?? [] as RouteStop[],
    isLoading,
    isError: !!error,
    refresh: mutate,
  }
}
