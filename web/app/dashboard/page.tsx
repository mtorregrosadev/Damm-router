"use client"

import { useState } from "react"
import dynamic from "next/dynamic"
import { LanguageProvider } from "@/web/lib/i18n"
import { Topbar } from "@/web/components/dashboard/topbar"
import { Sidebar } from "@/web/components/dashboard/sidebar"
import { mockTruckData } from "@/web/lib/mockData"

// Dynamic imports for heavy components
const RouteMap = dynamic(
  () => import("@/web/components/dashboard/route-map").then((mod) => mod.RouteMap),
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
  () => import("@/web/components/dashboard/truck-view").then((mod) => mod.TruckView),
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
  const [selectedStop, setSelectedStop] = useState<number | null>(null)
  const [showTruckView, setShowTruckView] = useState(false)

  return (
    <div className="flex h-screen flex-col bg-[#0B0F1C]">
      <Topbar />
      
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
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
              routeId="DR0006"
              driverId="DRV001"
              truckLoad={mockTruckData}
            />
          ) : (
            <RouteMap
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
