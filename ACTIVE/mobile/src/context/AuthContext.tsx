import React, { createContext, useContext, useEffect, useState } from 'react'
import { clearToken, getToken } from '../utils/api'

interface AuthContextValue {
  isLoggedIn: boolean
  isLoading: boolean
  markLoggedIn: () => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    getToken()
      .then((token) => setIsLoggedIn(!!token))
      .finally(() => setIsLoading(false))
  }, [])

  const markLoggedIn = () => setIsLoggedIn(true)
  const logout = async () => {
    await clearToken()
    setIsLoggedIn(false)
  }

  return (
    <AuthContext.Provider value={{ isLoggedIn, isLoading, markLoggedIn, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
