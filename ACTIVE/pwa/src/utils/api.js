const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'

function token() { return localStorage.getItem('iq_token') }

const DEV_USER = { id: 1, name: 'Расид', email: 'demo@iq-barakah.ru' }

const DEMO_EMAIL = 'demo@iq-barakah.ru'

async function req(method, path, body) {
  // Demo mode — backend not yet deployed
  const isDemo = token() === 'demo' || body?.email === DEMO_EMAIL
  if (isDemo) {
    if (path === '/me') return DEV_USER
    if (path === '/progress') return { tracker: {}, wheel: {}, ship: [] }
    if (path === '/auth/login' || path === '/auth/register') return { access_token: 'demo', user: DEV_USER }
    return { ok: true }
  }

  const headers = { 'Content-Type': 'application/json' }
  if (token()) headers['Authorization'] = `Bearer ${token()}`
  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Ошибка сети' }))
    throw new Error(err.detail || 'Ошибка')
  }
  return res.json()
}

export const api = {
  login:    (email, password) => req('POST', '/auth/login', { email, password }),
  register: (name, email, password) => req('POST', '/auth/register', { name, email, password }),
  me:       () => req('GET', '/me'),
  progress: () => req('GET', '/progress'),
  saveTracker: (data) => req('POST', '/tracker', data),
  saveWheel:   (data) => req('POST', '/wheel', data),
  saveShip:    (data) => req('POST', '/ship', data),
}

export function setToken(t) { localStorage.setItem('iq_token', t) }
export function clearToken() { localStorage.removeItem('iq_token') }
export function hasToken() { return !!token() }
