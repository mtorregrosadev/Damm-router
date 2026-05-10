import useSWR from "swr"
import type { RouteListItem, RoutesListResponse } from "@/lib/types/routes"

const fetcher = async (url: string): Promise<RouteListItem[]> => {
  const res  = await fetch(url)
  const json: RoutesListResponse = await res.json()
  if (!json.success) throw new Error(json.error || "Failed to fetch routes")
  return json.routes
}

export function useRoutes() {
  const { data, error, isLoading } = useSWR<RouteListItem[]>(
    "/api/routes",
    fetcher,
    { revalidateOnFocus: false, refreshInterval: 60000 }
  )
  return {
    routes:    data ?? [],
    isLoading,
    isError:   !!error,
  }
}
