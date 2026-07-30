import React, { createContext, useContext, useEffect, useState } from 'react'
import { loginWithTelegramWebApp } from '../utils/auth'
import { clearToken, getToken } from '../utils/api'
import { lsGet, lsSet } from '../utils/storage'

// Bumped from "seen_diagnostic" so every device re-runs the new onboarding once,
// regardless of whatever flag value an older build already persisted.
const SEEN_DIAGNOSTIC_KEY = 'seen_diagnostic_v2'

export type OnboardingStage = 'diagnostic' | 'vision' | 'done'

interface AuthContextValue {
  isLoggedIn: boolean
  isLoading: boolean
  onboarding: OnboardingStage | null
  markLoggedIn: () => void
  logout: () => Promise<void>
  advanceOnboarding: (stage: OnboardingStage) => void
  resetOnboarding: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [onboarding, setOnboarding] = useState<OnboardingStage | null>(null)

  useEffect(() => {
    let alive = true
    async function bootstrapAuth() {
      try {
        let token = await getToken()
        if (!token) {
          const loggedViaWebApp = await loginWithTelegramWebApp()
          if (loggedViaWebApp) token = await getToken()
        }
        if (alive) setIsLoggedIn(!!token)
      } finally {
        if (alive) setIsLoading(false)
      }
    }
    void bootstrapAuth()
    return () => { alive = false }
  }, [])

  useEffect(() => {
    if (!isLoggedIn) {
      setOnboarding(null)
      return
    }
    lsGet(SEEN_DIAGNOSTIC_KEY, false).then((seen) => setOnboarding(seen ? 'done' : 'diagnostic'))
  }, [isLoggedIn])

  const markLoggedIn = () => setIsLoggedIn(true)

  const logout = async () => {
    await clearToken()
    setIsLoggedIn(false)
  }

  const advanceOnboarding = (stage: OnboardingStage) => {
    if (stage === 'done') lsSet(SEEN_DIAGNOSTIC_KEY, true)
    setOnboarding(stage)
  }

  // Lets Profile offer "пройти диагностику заново" without forcing a full logout.
  const resetOnboarding = () => {
    lsSet(SEEN_DIAGNOSTIC_KEY, false)
    setOnboarding('diagnostic')
  }

  return (
    <AuthContext.Provider
      value={{ isLoggedIn, isLoading, onboarding, markLoggedIn, logout, advanceOnboarding, resetOnboarding }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
