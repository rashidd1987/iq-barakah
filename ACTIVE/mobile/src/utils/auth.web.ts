import { api, setToken } from './api'

const BOT_USERNAME = process.env.EXPO_PUBLIC_BOT_USERNAME || 'iqbaraka_bot'
const PENDING_SESSION_KEY = 'iq_mobile_tg_pending'

export type LoginStatus = 'opening_telegram' | 'waiting_confirmation' | 'success' | 'timeout' | 'error'

interface LoginOptions {
  onStatus?: (status: LoginStatus) => void
  timeoutMs?: number
  pollIntervalMs?: number
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
