import React, { createContext, useContext, useEffect, useState } from 'react'
import { loginWithTelegramWebApp } from '../utils/auth'
import { api, clearToken, getToken, MobileSessionStatus, setToken } from '../utils/api'
import { shouldClearTokenAfterSessionFailure } from '../utils/authSessionPolicy'
import { lsGet, lsSet } from '../utils/storage'

// Bumped from "seen_diagnostic" so every device re-runs the new onboarding once,
// regardless of whatever flag value an older build already persisted.
const SEEN_DIAGNOSTIC_KEY = 'seen_diagnostic_v2'

export type OnboardingStage = 'diagnostic' | 'vision' | 'done'
export type AuthStage = 'signed_out' | 'session_unavailable' | MobileSessionStatus

interface AuthContextValue {
  isLoggedIn: boolean
  isLoading: boolean
  authStage: AuthStage
  onboarding: OnboardingStage | null
  markLoggedIn: () => void
  acceptSession: (status: MobileSessionStatus, accessToken?: string) => Promise<void>
  refreshSession: () => Promise<void>
  logout: () => Promise<void>
  advanceOnboarding: (stage: OnboardingStage) => void
  resetOnboarding: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [authStage, setAuthStage] = useState<AuthStage>('signed_out')
  const [isLoading, setIsLoading] = useState(true)
  const [onboarding, setOnboarding] = useState<OnboardingStage | null>(null)

  useEffect(() => {
    let alive = true
    async function bootstrapAuth() {
      let token: string | null = null
      try {
        token = await getToken()
        if (!token) {
          const loggedViaWebApp = await loginWithTelegramWebApp()
          if (loggedViaWebApp) token = await getToken()
        }
        if (token) {
          const result = await api.resolveMobileSession()
          if (result.access_token) await setToken(result.access_token)
          if (alive) {
            setAuthStage(result.status)
            setIsLoggedIn(result.status === 'ok')
          }
        } else if (alive) {
          setAuthStage('signed_out')
          setIsLoggedIn(false)
        }
      } catch (error) {
        const invalid = shouldClearTokenAfterSessionFailure(error)
        if (invalid) await clearToken()
        if (alive) {
          setAuthStage(invalid || !token ? 'signed_out' : 'session_unavailable')
          setIsLoggedIn(false)
        }
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

  const markLoggedIn = () => {
    setAuthStage('ok')
    setIsLoggedIn(true)
  }

  const acceptSession = async (status: MobileSessionStatus, accessToken?: string) => {
    if (accessToken) await setToken(accessToken)
    setAuthStage(status)
    setIsLoggedIn(status === 'ok')
  }

  const refreshSession = async () => {
    setIsLoading(true)
    try {
      const result = await api.resolveMobileSession()
      await acceptSession(result.status, result.access_token)
    } catch (error) {
      if (shouldClearTokenAfterSessionFailure(error)) {
        await clearToken()
        setAuthStage('signed_out')
        setIsLoggedIn(false)
      } else {
        setAuthStage('session_unavailable')
        setIsLoggedIn(false)
      }
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    await clearToken()
    setAuthStage('signed_out')
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
      value={{ isLoggedIn, isLoading, authStage, onboarding, markLoggedIn, acceptSession, refreshSession, logout, advanceOnboarding, resetOnboarding }}
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
