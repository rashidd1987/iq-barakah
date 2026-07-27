import * as Linking from 'expo-linking'
import * as SecureStore from 'expo-secure-store'
import { AppState } from 'react-native'
import { ApiError, api, setToken } from './api'

const BOT_USERNAME = process.env.EXPO_PUBLIC_BOT_USERNAME || 'iqbaraka_bot'
const PENDING_SESSION_KEY = 'iq_mobile_tg_pending'

export type LoginStatus =
  | 'opening_telegram'
  | 'waiting_confirmation'
  | 'success'
  | 'timeout'
  | 'not_active'
  | 'expired'
  | 'error'

interface LoginOptions {
  onStatus?: (status: LoginStatus) => void
  timeoutMs?: number
  pollIntervalMs?: number
}

// Mirrors ACTIVE/pwa's tg-init -> bot confirm -> tg-check flow, using a native deep link
// instead of a browser redirect so it opens the Telegram app directly.
export async function loginWithTelegram(options: LoginOptions = {}): Promise<boolean> {
  const { onStatus, timeoutMs = 10 * 60 * 1000, pollIntervalMs = 2000 } = options

  let sessionId = await SecureStore.getItemAsync(PENDING_SESSION_KEY)

  // Android may recreate the app while Telegram is in the foreground. Reuse the
  // persisted session so the bot and the resumed app always refer to the same login.
  if (sessionId) {
    try {
      const existing = await api.tgCheck(sessionId)
      if (existing.status === 'ok' && existing.access_token) {
        await setToken(existing.access_token)
        await SecureStore.deleteItemAsync(PENDING_SESSION_KEY)
        onStatus?.('success')
        return true
      }
    } catch (error) {
      if (error instanceof ApiError && [403, 404, 410].includes(error.status)) {
        await SecureStore.deleteItemAsync(PENDING_SESSION_KEY)
        sessionId = null
      }
    }
  }

  if (!sessionId) {
    const created = await api.tgInit()
    sessionId = created.session_id
    await SecureStore.setItemAsync(PENDING_SESSION_KEY, sessionId)
  }
  const activeSessionId = sessionId

  onStatus?.('opening_telegram')
  await Linking.openURL(
    `https://t.me/${BOT_USERNAME}?start=pwa_${encodeURIComponent(activeSessionId)}`,
  )

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
        const result = await api.tgCheck(activeSessionId)
        if (result.status === 'ok' && result.access_token) {
          try {
            await setToken(result.access_token)
            await SecureStore.deleteItemAsync(PENDING_SESSION_KEY)
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
        if (error instanceof ApiError && error.status === 403) {
          await SecureStore.deleteItemAsync(PENDING_SESSION_KEY)
          onStatus?.('not_active')
          finish(false)
          return
        }
        if (error instanceof ApiError && [404, 410].includes(error.status)) {
          await SecureStore.deleteItemAsync(PENDING_SESSION_KEY)
          onStatus?.('expired')
          finish(false)
          return
        }
        // A temporary connection failure can recover on the next poll.
      } finally {
        checking = false
      }
      if (settled) return
      if (Date.now() >= deadline) {
        await SecureStore.deleteItemAsync(PENDING_SESSION_KEY)
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
