"use client"

import { useState } from "react"
import { Map, Truck, MessageSquare, LogOut, User } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { RouteMap } from "@/components/dashboard/route-map"
import { TruckView } from "@/components/dashboard/truck-view"
import { AiChat } from "@/components/dashboard/ai-chat"
import type { RouteStop, RouteSummary } from "@/lib/types/route-data"

interface MobileDashboardProps {
  summary: RouteSummary | null
  stops: RouteStop[]
  isLoading: boolean
  onLogout: () => void
  routeId: string
}

type Tab = "map" | "truck" | "ai"

export function MobileDashboard({
  summary,
  stops,
  isLoading,
  onLogout,
  routeId,
}: MobileDashboardProps) {
  const { t } = useLanguage()
  const [activeTab, setActiveTab] = useState<Tab>("map")
  const [selectedStop, setSelectedStop] = useState<number | null>(null)

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Mobile Top Header */}
      <header className="flex h-14 items-center justify-between border-b border-border bg-card px-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-white shadow-sm">
            DD
          </div>
          <div>
            <h1 className="text-xs font-bold text-foreground" style={{ fontFamily: 'var(--font-title)', textTransform: 'uppercase' }}>Damm Mobile</h1>
            <p className="text-[10px] text-muted-foreground">{summary?.ruta || routeId}</p>
          </div>
        </div>
        <button onClick={onLogout} className="text-muted-foreground hover:text-primary transition-colors">
          <LogOut className="h-5 w-5" />
        </button>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden relative">
        <div className={`h-full ${activeTab === "map" ? "block" : "hidden"}`}>
          <RouteMap
            stops={stops}
            summary={summary}
            selectedStop={selectedStop}
            onSelectStop={setSelectedStop}
          />
        </div>
        
        <div className={`h-full ${activeTab === "truck" ? "block" : "hidden"}`}>
          <TruckView
            selectedStop={selectedStop}
            onSelectStop={setSelectedStop}
            routeId={routeId}
            driverId="all"
            stopsData={stops}
          />
        </div>

        <div className={`h-full ${activeTab === "ai" ? "block" : "hidden"}`}>
          <AiChat />
        </div>
      </main>

      {/* Bottom Navigation */}
      <nav className="flex h-16 border-t border-border bg-card shadow-[0_-2px_10px_rgba(0,0,0,0.05)]">
        <NavButton
          active={activeTab === "map"}
          onClick={() => setActiveTab("map")}
          icon={<Map className="h-5 w-5" />}
          label="Mapa"
        />
        <NavButton
          active={activeTab === "truck"}
          onClick={() => setActiveTab("truck")}
          icon={<Truck className="h-5 w-5" />}
          label="Camió"
        />
        <NavButton
          active={activeTab === "ai"}
          onClick={() => setActiveTab("ai")}
          icon={<MessageSquare className="h-5 w-5" />}
          label="AI Chat"
        />
      </nav>
    </div>
  )
}

function NavButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-1 flex-col items-center justify-center gap-1 transition-colors ${
        active ? "text-primary" : "text-muted-foreground"
      }`}
    >
      <div className={`rounded-full px-4 py-1 transition-colors ${active ? "bg-primary/10" : ""}`}>
        {icon}
      </div>
      <span className="text-[10px] font-bold uppercase tracking-wider" style={{ fontFamily: 'var(--font-title)' }}>
        {label}
      </span>
    </button>
  )
}
