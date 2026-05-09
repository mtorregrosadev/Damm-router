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
    <div className="relative flex min-h-screen w-full items-center justify-center bg-[#0B0F1C]">
      {/* Language toggle in top-right corner */}
      <div className="absolute right-6 top-6">
        <LanguageToggle />
      </div>

      {/* Login card */}
      <div className="w-full max-w-[400px] rounded-xl border border-[#1E2A45] bg-[#10162A] p-12 shadow-2xl">
        {/* Truck icon */}
        <div className="mb-4 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#1A2340]">
            <Truck className="h-9 w-9 text-[#C8102E]" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-center text-[22px] font-medium text-white">
          {t.login.title}
        </h1>
        
        {/* Subtitle */}
        <p className="mt-1 text-center text-[13px] text-[#5570A0]">
          {t.login.subtitle}
        </p>

        {/* Divider */}
        <div className="my-6 h-px bg-[#1E2A45]" />

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-medium text-[#5570A0]">
              {t.login.username}
            </label>
            <Input
              type="text"
              placeholder="DA0216"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="h-11 border-[#1E2A45] bg-[#151D35] text-white placeholder:text-[#3A5A8C] focus:border-[#C8102E] focus:ring-[#C8102E]"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-[#5570A0]">
              {t.login.password}
            </label>
            <Input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-11 border-[#1E2A45] bg-[#151D35] text-white placeholder:text-[#3A5A8C] focus:border-[#C8102E] focus:ring-[#C8102E]"
            />
          </div>

          <Button
            type="submit"
            disabled={isLoading}
            className="mt-6 h-11 w-full rounded-lg bg-[#C8102E] text-white transition-colors hover:bg-[#A00D26] disabled:opacity-50"
          >
            {isLoading ? (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              t.login.enter
            )}
          </Button>
        </form>

        {/* Footer */}
        <p className="mt-8 text-center text-[11px] text-[#3A5A8C]">
          {t.login.footer}
        </p>
      </div>
    </div>
  )
}
