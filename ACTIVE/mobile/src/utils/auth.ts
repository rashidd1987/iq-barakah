import * as Linking from 'expo-linking'
import { AppState } from 'react-native'
import { ApiError, api, setToken } from './api'

const BOT_USERNAME = process.env.EXPO_PUBLIC_BOT_USERNAME || 'iqbaraka_bot'

export type LoginStatus = 'opening_telegram' | 'waiting_confirmation' | 'success' | 'timeout' | 'error'

interface LoginOptions {
  onStatus?: (status: LoginStatus) => void
  timeoutMs?: number
  pollIntervalMs?: number
}

// Mirrors ACTIVE/pwa's tg-init -> bot confirm -> tg-check flow, using a native deep link
// instead of a browser redirect so it opens the Telegram app directly.
export async function loginWithTelegram(options: LoginOptions = {}): Promise<boolean> {
  const { onStatus, timeoutMs = 10 * 60 * 1000, pollIntervalMs = 2000 } = options

  const { session_id } = await api.tgInit()

  onStatus?.('opening_telegram')
  await Linking.openURL(`https://t.me/${BOT_USERNAME}?start=pwa_${session_id}`)

  onStatus?.('waiting_confirmation')
  const deadline = Date.now() + timeoutMs

  return new Promise<boolean>((resolve) => {
    let settled = false
    let checking = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const finish = (result: boolean) => {
      if (settled) return
      settled = true
      if (timer) clearTimeout(timer)
      subscription.remove()
      resolve(result)
    }

    const checkOnce = async () => {
      if (settled || checking) return
      checking = true
      try {
        const result = await api.tgCheck(session_id)
        if (result.status === 'ok' && result.access_token) {
          try {
            await setToken(result.access_token)
          } catch {
            onStatus?.('error')
            finish(false)
            return
          }
          onStatus?.('success')
          finish(true)
          return
        }
      } catch (error) {
        if (error instanceof ApiError && [403, 404, 410].includes(error.status)) {
          onStatus?.('error')
          finish(false)
          return
        }
        // A temporary connection failure can recover on the next poll.
      } finally {
        checking = false
      }
      if (settled) return
      if (Date.now() >= deadline) {
        onStatus?.('timeout')
        finish(false)
        return
      }
      timer = setTimeout(checkOnce, pollIntervalMs)
    }

    // The OS throttles setTimeout while the app is backgrounded (which is exactly
    // when the user is over in Telegram confirming) — the timed poll can lag well
    // behind the confirmation. Re-check immediately the moment the app regains
    // focus instead of waiting for the next throttled tick.
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') checkOnce()
    })

    checkOnce()
  })
}
