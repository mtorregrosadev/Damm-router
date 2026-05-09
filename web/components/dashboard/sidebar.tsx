"use client"

import { Truck, Clock, MapPin, ArrowLeft } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { routeData, type Stop } from "@/lib/mock-data"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"

interface SidebarProps {
  selectedStop: number | null
  onSelectStop: (id: number | null) => void
  showTruckView: boolean
  onToggleTruckView: () => void
}

export function Sidebar({
  selectedStop,
  onSelectStop,
  showTruckView,
  onToggleTruckView,
}: SidebarProps) {
  const { t } = useLanguage()

  return (
    <aside className="flex w-[280px] flex-col border-r border-border bg-card">
      {/* Back button when in truck view */}
      {showTruckView && (
        <button
          onClick={onToggleTruckView}
          className="flex items-center gap-2 border-b border-border px-4 py-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {t.dashboard.backToMap}
        </button>
      )}

      {/* Truck summary card */}
      <div className="border-b border-border p-4">
        <span className="text-xs font-medium text-foreground" style={{ fontFamily: 'var(--font-ui)', fontWeight: 500 }}>{t.dashboard.truck}</span>
        
        {/* Truck illustration */}
        <div className="my-4 flex justify-center">
          <TruckIllustration />
        </div>

        {/* Look inside button */}
        <Button
          onClick={onToggleTruckView}
          variant="outline"
          className={`w-full border-primary text-primary hover:bg-primary hover:text-primary-foreground ${
            showTruckView ? "bg-primary text-primary-foreground" : ""
          }`}
        >
          {t.dashboard.lookInside}
        </Button>

        {/* Stats */}
        <div className="mt-4 grid grid-cols-3 gap-2">
          <div>
            <p className="text-[10px] text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>{t.dashboard.estimatedTime}</p>
            <p className="text-[13px] text-foreground" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>{routeData.estimatedTime}</p>
          </div>
          <div>
            <p className="text-[10px] text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>{t.dashboard.estimatedKm}</p>
            <p className="text-[13px] text-foreground" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>{routeData.estimatedKm} km</p>
          </div>
          <div>
            <p className="text-[10px] text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>Stops</p>
            <p className="text-[13px] text-foreground" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>{routeData.totalStops} {t.dashboard.stops}</p>
          </div>
        </div>
      </div>

      {/* Stops list */}
      <ScrollArea className="flex-1">
        <div className="p-3">
          {routeData.stops.map((stop) => (
            <StopCard
              key={stop.id}
              stop={stop}
              isSelected={selectedStop === stop.id}
              onClick={() => onSelectStop(selectedStop === stop.id ? null : stop.id)}
            />
          ))}
          
          {/* Return to warehouse */}
          <div className="mt-2 rounded-lg border border-border bg-muted p-3 opacity-60">
            <div className="flex items-center gap-3">
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-amber text-[10px] font-bold text-black">
                8
              </div>
              <div>
                <p className="text-xs font-semibold text-amber" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>
                  {t.dashboard.warehouse}
                </p>
                <p className="text-[10px] text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>Retorn</p>
              </div>
            </div>
          </div>
        </div>
      </ScrollArea>
    </aside>
  )
}

function StopCard({
  stop,
  isSelected,
  onClick,
}: {
  stop: Stop
  isSelected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`mb-2 w-full rounded-lg border p-3 text-left transition-all ${
        isSelected
          ? "border-primary bg-primary/10"
          : "border-border bg-muted hover:border-muted-foreground"
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Stop number */}
        <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
          {stop.id}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <p className="truncate text-xs font-semibold text-foreground" style={{ fontFamily: 'var(--font-ui)', fontWeight: 500 }}>{stop.name}</p>
          <p className="truncate text-[10px] text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>{stop.address}</p>
        </div>

        {/* Time window */}
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
          <Clock className="h-3 w-3" />
          {stop.timeWindow}
        </div>
      </div>

      {/* Returnables badge */}
      {stop.returnables && (
        <div className="mt-2 flex justify-end">
          <span className="rounded-full bg-green-light px-2 py-0.5 text-[10px] text-green" style={{ fontFamily: 'var(--font-data)' }}>
            ♻ {stop.returnables.count} {stop.returnables.type === "barrels" ? "barrils" : "caixes"}
          </span>
        </div>
      )}
    </button>
  )
}

function TruckIllustration() {
  return (
    <svg width="160" height="60" viewBox="0 0 160 60" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Truck body */}
      <rect x="10" y="15" width="100" height="35" rx="2" fill="var(--muted)" stroke="var(--border)" strokeWidth="1"/>
      
      {/* Cabin */}
      <path d="M110 25 L140 25 L145 35 L145 50 L110 50 Z" fill="var(--muted)" stroke="var(--border)" strokeWidth="1"/>
      
      {/* Window */}
      <rect x="115" y="28" width="22" height="12" rx="1" fill="var(--black)" stroke="var(--primary)" strokeWidth="0.5"/>
      
      {/* Wheels */}
      <circle cx="35" cy="50" r="8" fill="var(--black)" stroke="var(--border)" strokeWidth="2"/>
      <circle cx="85" cy="50" r="8" fill="var(--black)" stroke="var(--border)" strokeWidth="2"/>
      <circle cx="130" cy="50" r="8" fill="var(--black)" stroke="var(--border)" strokeWidth="2"/>
      
      {/* Wheel centers */}
      <circle cx="35" cy="50" r="3" fill="var(--primary)"/>
      <circle cx="85" cy="50" r="3" fill="var(--primary)"/>
      <circle cx="130" cy="50" r="3" fill="var(--primary)"/>
      
      {/* Load indicator boxes */}
      <rect x="20" y="22" width="15" height="12" fill="var(--primary)" opacity="0.8"/>
      <rect x="38" y="22" width="15" height="12" fill="var(--primary)" opacity="0.6"/>
      <rect x="56" y="22" width="15" height="12" fill="#3B82F6" opacity="0.8"/>
      <rect x="74" y="22" width="15" height="12" fill="var(--primary)" opacity="0.4"/>
      
      {/* Damm star */}
      <text x="125" y="47" fill="var(--primary)" fontSize="8" fontWeight="bold">*</text>
    </svg>
  )
}
