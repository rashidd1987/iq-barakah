import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { useColorScheme } from 'react-native'
import { ResolvedThemeMode, ThemeColors, ThemeMode, ThemePalette, themes } from '../theme/colors'
import { lsGet, lsSet } from '../utils/storage'

const PALETTE_KEY = 'theme_palette'
const MODE_KEY = 'theme_mode'

interface ThemeContextValue {
  colors: ThemeColors
  palette: ThemePalette
  mode: ThemeMode
  resolvedMode: ResolvedThemeMode
  isDark: boolean
  setPalette: (palette: ThemePalette) => void
  setMode: (mode: ThemeMode) => void
  toggleMode: () => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

function isPalette(value: unknown): value is ThemePalette {
  return value === 'classic' || value === 'feminine'
}

function isMode(value: unknown): value is ThemeMode {
  return value === 'system' || value === 'light' || value === 'dark'
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const systemScheme = useColorScheme()
  const [palette, setPaletteState] = useState<ThemePalette>('classic')
  const [mode, setModeState] = useState<ThemeMode>('system')

  useEffect(() => {
    Promise.all([lsGet<unknown>(PALETTE_KEY, 'classic'), lsGet<unknown>(MODE_KEY, 'system')]).then(
      ([savedPalette, savedMode]) => {
        if (isPalette(savedPalette)) setPaletteState(savedPalette)
        if (isMode(savedMode)) setModeState(savedMode)
      },
    )
  }, [])

  const setPalette = (next: ThemePalette) => {
    setPaletteState(next)
    void lsSet(PALETTE_KEY, next).catch(() => {})
  }

  const setMode = (next: ThemeMode) => {
    setModeState(next)
    void lsSet(MODE_KEY, next).catch(() => {})
  }

  const resolvedMode: ResolvedThemeMode = mode === 'system' ? (systemScheme === 'dark' ? 'dark' : 'light') : mode
  const colors = themes[palette][resolvedMode]

  const value = useMemo<ThemeContextValue>(
    () => ({
      colors,
      palette,
      mode,
      resolvedMode,
      isDark: resolvedMode === 'dark',
      setPalette,
      setMode,
      toggleMode: () => setMode(resolvedMode === 'dark' ? 'light' : 'dark'),
    }),
    [colors, mode, palette, resolvedMode],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext)
  if (!value) throw new Error('useTheme must be used within ThemeProvider')
  return value
}
