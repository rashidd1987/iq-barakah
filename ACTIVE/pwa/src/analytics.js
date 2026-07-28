// Lightweight privacy-first analytics — no external SDK, no cookies
// Sends anonymous events to our own backend

const QUEUE = []
let _uid = null

function uid() {
  if (_uid) return _uid
  _uid = localStorage.getItem('iq_auid')
  if (!_uid) {
    _uid = crypto.randomUUID?.() || Math.random().toString(36).slice(2)
    localStorage.setItem('iq_auid', _uid)
  }
  return _uid
}

export function track(event, props = {}) {
  const payload = {
    e: event,
    uid: uid(),
    ts: Date.now(),
    screen: document.getElementById('app')?.dataset?.screen || 'unknown',
    ...props,
  }
  QUEUE.push(payload)
  _flush()
}

let _flushTimer = null
function _flush() {
  if (_flushTimer) return
  _flushTimer = setTimeout(async () => {
    _flushTimer = null
    if (!QUEUE.length) return
    const batch = QUEUE.splice(0, QUEUE.length)
    try {
      const base = (import.meta.env?.VITE_API_URL) || 'http://localhost:8001'
      await fetch(`${base}/analytics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events: batch }),
        keepalive: true,
      })
    } catch {
      // silently fail — analytics must never break the app
    }
  }, 2000)
}

// Auto-track screen time
let _screenStart = Date.now()
let _currentScreen = 'home'

export function trackScreen(screen) {
  const spent = Math.round((Date.now() - _screenStart) / 1000)
  if (spent > 1) track('screen_time', { screen: _currentScreen, seconds: spent })
  _currentScreen = screen
  _screenStart = Date.now()
  track('screen_view', { screen })
}

// Track unhandled errors
window.addEventListener('error', e => {
  track('js_error', { msg: e.message?.slice(0, 120), file: e.filename?.split('/').pop() })
})
window.addEventListener('unhandledrejection', e => {
  track('promise_error', { msg: String(e.reason)?.slice(0, 120) })
})
