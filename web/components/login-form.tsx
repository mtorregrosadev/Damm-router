"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Truck } from "lucide-react"
import { LanguageToggle } from "@/components/language-toggle"
import { useLanguage } from "@/lib/i18n"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function LoginForm() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  const { t } = useLanguage()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    
    // Simulate login delay
    await new Promise((resolve) => setTimeout(resolve, 500))
    
    // Mock login - any credentials work
    router.push("/dashboard")
  }

  return (
    <div className="relative flex min-h-screen w-full items-center justify-center bg-background">
      {/* Language toggle in top-right corner */}
      <div className="absolute right-6 top-6">
        <LanguageToggle />
      </div>

      {/* Login card */}
      <div className="w-full max-w-[400px] rounded-xl border border-border bg-card p-12" style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
        {/* Truck icon */}
        <div className="mb-4 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <Truck className="h-9 w-9 text-primary" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-center text-[22px] font-medium text-foreground" style={{ fontFamily: 'var(--font-title)', fontWeight: 800, textTransform: 'uppercase' }}>
          {t.login.title}
        </h1>
        
        {/* Subtitle */}
        <p className="mt-1 text-center text-[13px] text-muted-foreground" style={{ fontFamily: 'var(--font-ui)', fontWeight: 400 }}>
          {t.login.subtitle}
        </p>

        {/* Divider */}
        <div className="my-6 h-px bg-border" />

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground" style={{ fontFamily: 'var(--font-ui)', fontWeight: 500 }}>
              {t.login.username}
            </label>
            <Input
              type="text"
              placeholder="DA0216"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="h-11 border-border bg-card text-foreground placeholder:text-muted-foreground focus:border-primary focus:ring-primary"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground" style={{ fontFamily: 'var(--font-ui)', fontWeight: 500 }}>
              {t.login.password}
            </label>
            <Input
              type="password"
              placeholder="•••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-11 border-border bg-card text-foreground placeholder:text-muted-foreground focus:border-primary focus:ring-primary"
            />
          </div>

          <Button
            type="submit"
            disabled={isLoading}
            className="mt-6 h-11 w-full rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {isLoading ? (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              t.login.enter
            )}
          </Button>
        </form>

        {/* Footer */}
        <p className="mt-8 text-center text-[11px] text-muted-foreground" style={{ fontFamily: 'var(--font-data)' }}>
          {t.login.footer}
        </p>
      </div>
    </div>
  )
}
