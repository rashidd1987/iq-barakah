import * as Linking from 'expo-linking'
import { api, setToken } from './api'

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

  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs))
    try {
      const result = await api.tgCheck(session_id)
      if (result.status === 'ok' && result.access_token) {
        await setToken(result.access_token)
        onStatus?.('success')
        return true
      }
    } catch {
      // transient network error while polling — keep trying until timeout
    }
  }

  onStatus?.('timeout')
  return false
}
