"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"

export const AUTH_KEY = "damm_route_session"

export interface AuthSession {
  ruta: string
  data: string
}

export function useAuth() {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [initialized, setInitialized] = useState(false)
  const router = useRouter()

  useEffect(() => {
    const stored = localStorage.getItem(AUTH_KEY)
    if (stored) {
      try {
        setSession(JSON.parse(stored))
      } catch {
        localStorage.removeItem(AUTH_KEY)
      }
    }
    setInitialized(true)
  }, [])

  const login = (s: AuthSession) => {
    localStorage.setItem(AUTH_KEY, JSON.stringify(s))
    setSession(s)
  }

  const logout = () => {
    localStorage.removeItem(AUTH_KEY)
    setSession(null)
    router.push("/")
  }

  const switchRoute = (s: AuthSession) => {
    localStorage.setItem(AUTH_KEY, JSON.stringify(s))
    setSession(s)
  }

  return { session, initialized, login, logout, switchRoute }
}
