"use client"

import { ArrowLeft, Clock } from "lucide-react"
import { useLanguage } from "@/lib/i18n"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { RouteStop, RouteSummary } from "@/lib/types/route-data"

interface SidebarProps {
  summary: RouteSummary | null
  stops: RouteStop[]
  isLoading: boolean
  selectedStop: number | null
  onSelectStop: (ordre: number | null) => void
  showTruckView: boolean
  onToggleTruckView: () => void
}

function formatMinutes(totalMin: number): string {
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  if (h > 0) {
    return m > 0 ? `${h}h ${m}min` : `${h}h`
  }
  return `${m}min`
}

export function Sidebar({
  summary,
  stops,
  isLoading,
  selectedStop,
  onSelectStop,
  showTruckView,
  onToggleTruckView,
}: SidebarProps) {
  const { t } = useLanguage()

  // Deduplicate stops by ordre for the count (shared stops share same ordre)
  const uniqueOrdres = new Set(stops.map(s => s.ordre)).size

  return (
    <aside className="flex w-[400px] flex-col border-r border-border bg-card overflow-hidden">
      {/* Back button when in truck view */}
      {showTruckView && (
        <button
          onClick={onToggleTruckView}
          className="flex items-center gap-2 border-b border-border px-8 py-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {t.dashboard.backToMap}
        </button>
      )}

      {/* Truck summary card */}
      <div className="border-b border-border p-8">
        <span className="text-xs font-medium text-foreground uppercase tracking-widest" style={{ fontFamily: 'var(--font-ui)', fontWeight: 600 }}>
          {t.dashboard.truck}
        </span>

        {/* Truck illustration */}
        {!showTruckView && (
          <div className="my-6 flex justify-center">
            <TruckIllustration />
          </div>
        )}

        {/* Look inside button */}
        {!showTruckView && (
          <Button
            onClick={onToggleTruckView}
            variant="outline"
            className="w-full border-primary text-primary hover:bg-primary hover:text-primary-foreground h-11 text-sm font-bold uppercase tracking-wider"
          >
            {t.dashboard.lookInside}
          </Button>
        )}

        {/* Stats */}
        <div className="mt-8 grid grid-cols-2 gap-6">
          <div>
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1" style={{ fontFamily: 'var(--font-data)' }}>
              {t.dashboard.estimatedTime}
            </p>
            <p className="text-[16px] text-foreground" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>
              {summary ? formatMinutes(summary.temps_total_min) : "—"}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1" style={{ fontFamily: 'var(--font-data)' }}>Stops</p>
            <p className="text-[16px] text-foreground" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>
              {summary ? summary.clients_visitats : "—"} {t.dashboard.stops}
            </p>
          </div>
        </div>
      </div>

      {/* Stops list */}
      <ScrollArea className="flex-1 min-h-0 w-full">
        <div className="px-8 py-6">
          {isLoading ? (
            <div className="py-8 text-center text-xs text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
              {t.stops.loadingRoute}
            </div>
          ) : stops.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
              {t.stops.noData}
            </div>
          ) : (
            stops.map((stop, idx) => (
              <StopCard
                key={`${stop.ordre}-${idx}`}
                stop={stop}
                isSelected={selectedStop === stop.ordre}
                onClick={() => onSelectStop(selectedStop === stop.ordre ? null : stop.ordre)}
              />
            ))
          )}

          {/* Return to warehouse */}
          {!isLoading && stops.length > 0 && (
            <div className="mt-2 rounded-lg border border-border bg-muted p-3 opacity-60">
              <div className="flex items-center gap-3">
                <div className="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold"
                  style={{ background: 'var(--amber)', color: 'var(--black)' }}>
                  ↩
                </div>
                <div>
                  <p className="text-xs font-semibold" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase', color: 'var(--amber)' }}>
                    {t.dashboard.warehouse}
                  </p>
                  <p className="text-[10px] text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
                    {t.stops.return}
                  </p>
                </div>
              </div>
            </div>
          )}
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
  stop: RouteStop
  isSelected: boolean
  onClick: () => void
}) {
  const { t } = useLanguage()

  return (
    <button
      onClick={onClick}
      className={`mb-3 w-full rounded-xl border p-4 text-left transition-all ${
        isSelected
          ? "border-primary bg-primary/5 ring-1 ring-primary/20"
          : "border-border bg-muted/30 hover:border-muted-foreground/30 hover:bg-muted/50"
      }`}
    >
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-3 min-w-0">
          {/* Stop number */}
          <div className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-primary-foreground ${stop.fora_franja ? 'bg-amber' : 'bg-primary'}`}>
            {stop.ordre}
          </div>

          {/* Info */}
          <div className="min-w-0">
            <p className="truncate text-[13px] font-bold text-foreground" style={{ fontFamily: 'var(--font-ui)' }}>
              {stop.nom}
            </p>
          </div>
        </div>

        {/* Arrival time */}
        <div className="flex flex-shrink-0 items-center gap-1 text-[11px] font-semibold text-muted-foreground bg-white px-2 py-0.5 rounded-md border border-border/50" style={{ fontFamily: 'var(--font-data)' }}>
          <Clock className="h-3 w-3" />
          {stop.hora}
        </div>
      </div>

      <p className="truncate text-[10px] text-muted-foreground mb-3 pl-9" style={{ fontFamily: 'var(--font-data)' }}>
        {stop.zona}
      </p>

      {/* Badges row */}
      <div className="flex flex-wrap gap-1 pl-9">
        {stop.temps_descarrega > 0 && (
          <span className="rounded-full px-2 py-0.5 text-[10px]"
            style={{ fontFamily: 'var(--font-data)', background: 'var(--blue-light)', color: 'var(--blue-info)' }}>
            {stop.temps_descarrega} {t.stops.unloadTime}
          </span>
        )}
        {stop.parada_compartida !== null && (
          <span className="rounded-full px-2 py-0.5 text-[10px]"
            style={{ fontFamily: 'var(--font-data)', background: 'var(--amber-light)', color: 'var(--amber)' }}>
            #{stop.parada_compartida} {t.stops.sharedStop}
          </span>
        )}
        {stop.fora_franja && (
          <span className="rounded-full px-2 py-0.5 text-[10px]"
            style={{ fontFamily: 'var(--font-data)', background: 'var(--red-light)', color: 'var(--red)' }}>
            ⚠ {t.stops.outOfWindow}
          </span>
        )}
      </div>
    </button>
  )
}

function TruckIllustration() {
  return (
    <svg width="160" height="60" viewBox="0 0 160 60" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="10" y="15" width="100" height="35" rx="2" fill="var(--muted)" stroke="var(--border)" strokeWidth="1"/>
      <path d="M110 25 L140 25 L145 35 L145 50 L110 50 Z" fill="var(--muted)" stroke="var(--border)" strokeWidth="1"/>
      <rect x="115" y="28" width="22" height="12" rx="1" fill="var(--black)" stroke="var(--primary)" strokeWidth="0.5"/>
      <circle cx="35" cy="50" r="8" fill="var(--black)" stroke="var(--border)" strokeWidth="2"/>
      <circle cx="85" cy="50" r="8" fill="var(--black)" stroke="var(--border)" strokeWidth="2"/>
      <circle cx="130" cy="50" r="8" fill="var(--black)" stroke="var(--border)" strokeWidth="2"/>
      <circle cx="35" cy="50" r="3" fill="var(--primary)"/>
      <circle cx="85" cy="50" r="3" fill="var(--primary)"/>
      <circle cx="130" cy="50" r="3" fill="var(--primary)"/>
      <rect x="20" y="22" width="15" height="12" fill="var(--primary)" opacity="0.8"/>
      <rect x="38" y="22" width="15" height="12" fill="var(--primary)" opacity="0.6"/>
      <rect x="56" y="22" width="15" height="12" fill="#3B82F6" opacity="0.8"/>
      <rect x="74" y="22" width="15" height="12" fill="var(--primary)" opacity="0.4"/>
      <text x="125" y="47" fill="var(--primary)" fontSize="8" fontWeight="bold">*</text>
    </svg>
  )
}
