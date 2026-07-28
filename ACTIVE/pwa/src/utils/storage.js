const PREFIX = 'iq_'

export function lsGet(key, fallback = null) {
  try {
    const v = localStorage.getItem(PREFIX + key)
    return v !== null ? JSON.parse(v) : fallback
  } catch { return fallback }
}

export function lsSet(key, value) {
  localStorage.setItem(PREFIX + key, JSON.stringify(value))
}

export function todayKey() {
  return new Date().toISOString().split('T')[0]
}
