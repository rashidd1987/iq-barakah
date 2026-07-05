import * as SecureStore from 'expo-secure-store'

// Points at ACTIVE/pwa_api (extended with /mobile/* routes). Override with EXPO_PUBLIC_API_URL for local dev.
const BASE = process.env.EXPO_PUBLIC_API_URL || 'https://pwa-api.iq-barakah.ru'

const TOKEN_KEY = 'iq_jwt'

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY)
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token)
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${res.status} ${path}: ${body}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),

  tgInit: () => api.post<{ session_id: string }>('/mobile/auth/tg-init'),
  tgCheck: (sessionId: string) =>
    api.get<{ status: 'pending' | 'ok'; access_token?: string }>(
      `/mobile/auth/tg-check?session_id=${encodeURIComponent(sessionId)}`,
    ),

  participant: () =>
    api.get<{ level: string; week: number; vakt_level: string | null; is_active: boolean }>(
      '/mobile/participant',
    ),

  content: (level: string, week: number) =>
    api.get<{
      title: string
      hadith: string
      text: Record<'I' | 'II' | 'III', string>
      tasks: Record<'I' | 'II' | 'III', string[]>
    }>(`/mobile/content/${encodeURIComponent(level)}/${week}`),

  weekAck: (level: string, week: number) =>
    api.post<{ ok: boolean; graduated: boolean }>('/mobile/week-ack', { level, week }),

  tracker: (days = 30) =>
    api.get<{ date: string; habits: Record<string, Record<string, boolean>> }[]>(
      `/mobile/tracker?days=${days}`,
    ),
  saveTracker: (date: string, habits: Record<string, unknown>) =>
    api.post('/mobile/tracker', { date, habits }),

  registerPush: (expoToken: string, platform: string) =>
    api.post('/push/register', { expo_token: expoToken, platform }),

  cohortCount: () => api.get<{ count: number }>('/mobile/cohort-count'),
}
