"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import dynamic from "next/dynamic"
import { LanguageProvider } from "@/lib/i18n"
import { Topbar } from "@/components/dashboard/topbar"
import { Sidebar } from "@/components/dashboard/sidebar"
import { useRouteData } from "@/hooks/use-route-data"
import { AUTH_KEY } from "@/hooks/use-auth"
import type { AuthSession } from "@/hooks/use-auth"

const RouteMap = dynamic(
  () => import("@/components/dashboard/route-map").then((mod) => mod.RouteMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center bg-[#0B0F1C]">
        <div className="text-[#5570A0]">Loading map...</div>
      </div>
    ),
  }
)

const TruckView = dynamic(
  () => import("@/components/dashboard/truck-view").then((mod) => mod.TruckView),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center bg-[#0B0F1C]">
        <div className="text-[#5570A0]">Loading 3D view...</div>
      </div>
    ),
  }
)

function DashboardContent() {
  const router = useRouter()
  const [selectedStop, setSelectedStop] = useState<number | null>(null)
  const [showTruckView, setShowTruckView] = useState(false)
  const [session, setSession] = useState<AuthSession | null>(null)
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem(AUTH_KEY)
    if (!stored) {
      router.replace("/")
      return
    }
    try {
      setSession(JSON.parse(stored))
    } catch {
      localStorage.removeItem(AUTH_KEY)
      router.replace("/")
      return
    }
    setAuthChecked(true)
  }, [router])

  const { summary, stops, isLoading } = useRouteData(session?.ruta, session?.data)

  const handleLogout = () => {
    localStorage.removeItem(AUTH_KEY)
    router.replace("/")
  }

  const handleRouteChange = (ruta: string, data: string) => {
    const s: AuthSession = { ruta, data }
    localStorage.setItem(AUTH_KEY, JSON.stringify(s))
    setSession(s)
  }

  if (!authChecked) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-[#0B0F1C]">
      <Topbar
        summary={summary}
        onLogout={handleLogout}
        onRouteChange={handleRouteChange}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          summary={summary}
          stops={stops}
          isLoading={isLoading}
          selectedStop={selectedStop}
          onSelectStop={setSelectedStop}
          showTruckView={showTruckView}
          onToggleTruckView={() => setShowTruckView(!showTruckView)}
        />

        <main className="flex-1 overflow-hidden">
          {showTruckView ? (
            <TruckView
              selectedStop={selectedStop}
              onSelectStop={setSelectedStop}
              routeId={summary?.ruta ?? session?.ruta ?? ""}
              driverId="all"
            />
          ) : (
            <RouteMap
              stops={stops}
              summary={summary}
              selectedStop={selectedStop}
              onSelectStop={setSelectedStop}
            />
          )}
        </main>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  return (
    <LanguageProvider>
      <DashboardContent />
    </LanguageProvider>
  )
}
