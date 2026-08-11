import { api, setToken } from './api'

const BOT_USERNAME = process.env.EXPO_PUBLIC_BOT_USERNAME || 'iqbaraka_bot'
const PENDING_SESSION_KEY = 'iq_mobile_tg_pending'
const TELEGRAM_SDK_TIMEOUT_MS = 4_000
const TELEGRAM_AUTH_TIMEOUT_MS = 8_000

export type LoginStatus = 'opening_telegram' | 'waiting_confirmation' | 'success' | 'timeout' | 'error'

interface LoginOptions {
  onStatus?: (status: LoginStatus) => void
  timeoutMs?: number
  pollIntervalMs?: number
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp
    }
  }
}

interface TelegramWebApp {
  initData?: string
  ready?: () => void
  expand?: () => void
}

async function ensureTelegramWebApp(): Promise<TelegramWebApp | null> {
  if (window.Telegram?.WebApp) return window.Telegram.WebApp
  if (document.querySelector('script[data-telegram-web-app]')) {
    await waitForTelegramSdk(TELEGRAM_SDK_TIMEOUT_MS)
    return window.Telegram?.WebApp ?? null
  }

  await new Promise<void>((resolve) => {
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-web-app.js'
    script.async = true
    script.dataset.telegramWebApp = 'true'
    let settled = false
    const finish = () => {
      if (settled) return
      settled = true
      window.clearTimeout(timeout)
      script.onload = null
      script.onerror = null
      resolve()
    }
    const timeout = window.setTimeout(finish, TELEGRAM_SDK_TIMEOUT_MS)
    script.onload = finish
    script.onerror = finish
    document.head.appendChild(script)
  })
  return window.Telegram?.WebApp ?? null
}

function waitForTelegramSdk(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs
  return new Promise((resolve) => {
    const check = () => {
      if (window.Telegram?.WebApp || Date.now() >= deadline) {
        resolve()
        return
      }
      window.setTimeout(check, 50)
    }
    check()
  })
}

async function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  let timeout: number | undefined
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_, reject) => {
        timeout = window.setTimeout(
          () => reject(new Error('Telegram authentication timed out')),
          timeoutMs,
        )
      }),
    ])
  } finally {
    if (timeout !== undefined) window.clearTimeout(timeout)
  }
}

export async function loginWithTelegramWebApp(): Promise<boolean> {
  const webApp = await ensureTelegramWebApp()
  const initData = webApp?.initData
  if (!initData) return false

  try {
    webApp?.ready?.()
    webApp?.expand?.()
    const result = await withTimeout(
      api.telegramWebAppAuth(initData),
      TELEGRAM_AUTH_TIMEOUT_MS,
    )
    await setToken(result.access_token)
    return true
  } catch {
    return false
  }
}

export async function loginWithTelegram(options: LoginOptions = {}): Promise<boolean> {
  const { onStatus, timeoutMs = 10 * 60 * 1000, pollIntervalMs = 2000 } = options
  const { session_id } = await api.tgInit()
  window.localStorage.setItem(PENDING_SESSION_KEY, session_id)

  onStatus?.('opening_telegram')
  const telegramWindow = window.open(
    `https://t.me/${BOT_USERNAME}?start=pwa_${encodeURIComponent(session_id)}`,
    '_blank',
  )
  if (!telegramWindow) {
    window.location.assign(`https://t.me/${BOT_USERNAME}?start=pwa_${encodeURIComponent(session_id)}`)
    return false
  }

  onStatus?.('waiting_confirmation')
  const deadline = Date.now() + timeoutMs

  return new Promise<boolean>((resolve) => {
    let settled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const finish = (result: boolean) => {
      if (settled) return
      settled = true
      if (timer) clearTimeout(timer)
      document.removeEventListener('visibilitychange', checkWhenVisible)
      if (result) window.localStorage.removeItem(PENDING_SESSION_KEY)
      resolve(result)
    }

    const checkOnce = async () => {
      if (settled) return
      try {
        const result = await api.tgCheck(session_id)
        if (result.status === 'ok' && result.access_token) {
          await setToken(result.access_token)
          onStatus?.('success')
          finish(true)
          return
        }
      } catch {
        // A short network interruption should not abort the login window.
      }
      if (Date.now() >= deadline) {
        onStatus?.('timeout')
        window.localStorage.removeItem(PENDING_SESSION_KEY)
        finish(false)
        return
      }
      timer = setTimeout(checkOnce, pollIntervalMs)
    }

    const checkWhenVisible = () => {
      if (document.visibilityState === 'visible') void checkOnce()
    }

    document.addEventListener('visibilitychange', checkWhenVisible)
    void checkOnce()
  })
}
