const BASE = process.env.EXPO_PUBLIC_API_URL || 'https://pwa-api.iq-barakah.ru'
const TOKEN_KEY = 'iq_mobile_jwt'

export async function getToken(): Promise<string | null> {
  return window.localStorage.getItem(TOKEN_KEY)
}

export async function setToken(token: string): Promise<void> {
  window.localStorage.setItem(TOKEN_KEY, token)
}

export async function clearToken(): Promise<void> {
  window.localStorage.removeItem(TOKEN_KEY)
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
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),

  tgInit: () => api.post<{ session_id: string }>('/mobile/auth/tg-init'),
  tgCheck: (sessionId: string) =>
    api.get<{ status: 'pending' | 'ok'; access_token?: string }>(
      `/mobile/auth/tg-check?session_id=${encodeURIComponent(sessionId)}`,
    ),
  participant: () =>
    api.get<{ level: string; week: number; vakt_level: string | null; is_active: boolean }>(
      '/mobile/participant',
    ),
  profile: () => api.get<MobileProfile>('/mobile/profile'),
  updateProfile: (body: { name: string; email: string | null; phone: string | null }) =>
    api.put<{ ok: boolean }>('/mobile/profile', body),
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
  quiz: (level: string, week: number) =>
    api.get<Record<'I' | 'II' | 'III', QuizQuestion[]>>(
      `/mobile/quiz/${encodeURIComponent(level)}/${week}`,
    ),
  getWheel: () =>
    api.get<{ scores: Record<string, number> | null; created_at: string | null }>('/mobile/wheel'),
  saveWheel: (scores: Record<string, number>) => api.post('/mobile/wheel', { scores }),
  saveMuhasaba: (answers: { q: string; a: string }[]) =>
    api.post<{ ok: boolean; reflection: string }>('/mobile/muhasaba', { answers }),
  muhasabaStreak: () => api.get<{ streak: number; done_today: boolean }>('/mobile/muhasaba/streak'),
  activityFeed: (limit = 20) => api.get<ActivityItem[]>(`/mobile/activity-feed?limit=${limit}`),
}

export interface ActivityItem {
  first_name: string
  level: string
  global_week: number
  acked_at: string
  is_me: boolean
}

export interface QuizQuestion {
  q: string
  opts: string[]
  correct: number
}

export interface MobileProfile {
  personal: {
    name: string
    username: string | null
    email: string | null
    phone: string | null
    auth_provider: 'telegram'
    member_since: string | null
  }
  program: {
    level: string | null
    week: number | null
    vakt_level: string | null
    is_active: boolean
    activated_at: string | null
    graduated_at: string | null
    weeks_completed: number
    tasks_completed: number
    tracker_days: number
    muhasaba_count: number
    diagnostics_count: number
    first_step_at: string | null
    last_step_at: string | null
  }
  referral: {
    code: string
    link: string
    invited_count: number
    active_count: number
    graduated_count: number
    paid_count: number
    paid_total: number
    barakah_balance: number
    people: {
      first_name: string
      level: string | null
      week: number | null
      is_active: boolean
      graduated: boolean
      completed_steps: number
      has_paid: boolean
    }[]
  }
  charity: {
    percent: number
    own_reserved: number
    referral_reserved: number
    community_reserved: number
    transferred: number | null
    basis: 'paid_non_refunded'
  }
  payments: { paid_total: number; payments_count: number }
}
