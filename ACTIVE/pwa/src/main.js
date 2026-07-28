import { api, setToken, clearToken, hasToken } from './utils/api.js'
import { initI18n } from './i18n.js'
import { showGlossaryTip } from './components/sheets.js'
import { initHome, U } from './screens/home.js'
import { setCurrentWeek } from './screens/lessons.js'
import { renderTracker } from './screens/tracker.js'
import { initApp, rerenderCurrentScreen } from './app.js'
import { initDiagnostic, openDiag } from './components/diagnostic.js'
import { initReviewSheet, openReviewSheet } from './components/sheets.js'
import { WEEKS } from './data/weeks.js'
import { lsGet, lsSet } from './utils/storage.js'
import { isChecked } from './screens/tracker.js'
import { NAMAZ, DAILY } from './data/habits.js'
import { PROGRAM_TASKS } from './data/tasks.js'
import { initOnboarding } from './onboarding.js'
import { track } from './analytics.js'
import { requestPushPermission, initDailyReminder, getReminderTime, setReminderTime } from './push.js'
import { exportProgress, exportProgressCSV } from './export.js'
import { openPaywall, isPremium } from './paywall.js'
import { applyParticipantProgress } from './utils/participant-progress.js'

const BOT_USERNAME = 'iqbaraka_bot'
const TG_POLL_INTERVAL_MS = 2000
const TG_LOGIN_TIMEOUT_MS = 10 * 60 * 1000
const TG_PENDING_SESSION_KEY = 'iq_tg_pending_session'

// ── OFFLINE BANNER ────────────────────────────────────────────────────────────
;(function() {
  const banner = document.createElement('div')
  banner.id = 'offline-banner'
  banner.textContent = '📵 Нет сети — работаем офлайн'
  document.body.appendChild(banner)
  const update = () => banner.classList.toggle('show', !navigator.onLine)
  window.addEventListener('online', update)
  window.addEventListener('offline', update)
  update()
})()

// ── ERROR TOAST ────────────────────────────────────────────────────────────────
;(function() {
  const toast = document.createElement('div')
  toast.id = 'err-toast'
  toast.innerHTML = '<span id="err-toast-msg"></span><button onclick="document.getElementById(\'err-toast\').classList.remove(\'show\')">✕</button>'
  document.body.appendChild(toast)
  window.__showErrToast = (msg) => {
    document.getElementById('err-toast-msg').textContent = msg
    toast.classList.add('show')
    setTimeout(() => toast.classList.remove('show'), 5000)
  }
  window.addEventListener('error', e => {
    if (e.message?.includes('ResizeObserver')) return // benign
    window.__showErrToast('Что-то пошло не так. Попробуйте обновить страницу.')
  })
})()

// expose paywall globally for screens
window.openPaywall = openPaywall
window.isPremium = isPremium

// ── AUTH ─────────────────────────────────────────────────────────────────────

window.__showLogin = window.showLogin = function() {
  document.getElementById('auth-login-form').classList.remove('hidden')
  document.getElementById('auth-register-form').classList.add('hidden')
}
window.__showRegister = window.showRegister = function() {
  document.getElementById('auth-login-form').classList.add('hidden')
  document.getElementById('auth-register-form').classList.remove('hidden')
}

window.__authLogin = window.authLogin = async function() {
  const email  = document.getElementById('inp-email').value.trim()
  const pass   = document.getElementById('inp-pass').value
  const errEl  = document.getElementById('auth-err')
  const btnTxt = document.getElementById('btn-login-txt')
  const spin   = document.getElementById('btn-login-spin')
  if (!email || !pass) { errEl.textContent = 'Заполните все поля'; return }
  errEl.textContent = ''
  btnTxt.style.display = 'none'; spin.style.display = 'inline-block'
  try {
    const data = await api.login(email, pass)
    setToken(data.access_token)
    if (data.user) localStorage.setItem('iq_user', JSON.stringify(data.user))
    await enterApp()
  } catch (e) {
    errEl.textContent = e.message
  } finally {
    btnTxt.style.display = ''; spin.style.display = 'none'
  }
}

window.__authRegister = window.authRegister = async function() {
  const name   = document.getElementById('inp-name').value.trim()
  const email  = document.getElementById('inp-reg-email').value.trim()
  const pass   = document.getElementById('inp-reg-pass').value
  const errEl  = document.getElementById('reg-err')
  const btnTxt = document.getElementById('btn-reg-txt')
  const spin   = document.getElementById('btn-reg-spin')
  if (!name || !email || !pass) { errEl.textContent = 'Заполните все поля'; return }
  if (pass.length < 8) { errEl.textContent = 'Пароль минимум 8 символов'; return }
  errEl.textContent = ''
  btnTxt.style.display = 'none'; spin.style.display = 'inline-block'
  try {
    const data = await api.register(name, email, pass)
    setToken(data.access_token)
    localStorage.setItem('iq_user', JSON.stringify({ name }))
    await enterApp(true) // new user → show onboarding
  } catch (e) {
    errEl.textContent = e.message
  } finally {
    btnTxt.style.display = ''; spin.style.display = 'none'
  }
}

async function completeTelegramLogin(sessionId) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < TG_LOGIN_TIMEOUT_MS) {
    await new Promise(resolve => setTimeout(resolve, TG_POLL_INTERVAL_MS))
    const result = await api.telegramCheck(sessionId)
    if (result.status !== 'ok') continue
    setToken(result.access_token)
    localStorage.removeItem(TG_PENDING_SESSION_KEY)
    const user = await api.me()
    localStorage.setItem('iq_user', JSON.stringify(user))
    window.location.reload()
    return true
  }
  localStorage.removeItem(TG_PENDING_SESSION_KEY)
  throw new Error('Время подтверждения истекло. Попробуйте ещё раз.')
}

window.authTelegram = async function() {
  const button = document.getElementById('btn-tg-login')
  const errEl = document.getElementById('auth-err')
  const originalHtml = button?.innerHTML
  if (button) {
    button.disabled = true
    button.textContent = 'Ожидаем подтверждение…'
  }
  if (errEl) errEl.textContent = 'Подтвердите вход в Telegram, затем вернитесь сюда.'

  try {
    const { session_id: sessionId } = await api.telegramInit()
    localStorage.setItem(TG_PENDING_SESSION_KEY, sessionId)
    window.location.href = `https://t.me/${BOT_USERNAME}?start=pwa_${encodeURIComponent(sessionId)}`
    await completeTelegramLogin(sessionId)
  } catch (error) {
    localStorage.removeItem(TG_PENDING_SESSION_KEY)
    if (errEl) errEl.textContent = error.message || 'Не удалось войти через Telegram.'
  } finally {
    if (button) {
      button.disabled = false
      if (originalHtml) button.innerHTML = originalHtml
    }
  }
}

// ── APP INIT ─────────────────────────────────────────────────────────────────

async function syncParticipantProgress() {
  const data = await api.progress()
  return applyParticipantProgress(data.participant, U, lsSet)
}

function showParticipantLinkBanner() {
  if (document.getElementById('participant-link-banner')) return
  const banner = document.createElement('div')
  banner.id = 'participant-link-banner'
  banner.style.cssText = 'margin:12px 16px 0;padding:14px;border-radius:16px;background:#fff7df;border:1px solid #e7cc7b;color:#173d2a;font-size:13px;line-height:1.45;box-shadow:0 4px 16px rgba(23,61,42,.08)'
  banner.innerHTML = '<strong>Синхронизируйте прогресс</strong><div style="margin-top:3px;color:#59635b">Привяжите Telegram, чтобы PWA показывала тот же шаг, что бот и приложение.</div><button type="button" style="margin-top:10px;width:100%;padding:10px 12px;border:0;border-radius:12px;background:#2e6847;color:white;font-weight:700">Привязать Telegram</button>'
  banner.querySelector('button').addEventListener('click', () => window.authTelegram())
  document.querySelector('#sc-home .hdr')?.after(banner)
}

async function enterApp(isNewUser = false) {
  document.getElementById('auth-screen').classList.add('hidden')

  let participantLinked = false
  try {
    participantLinked = await syncParticipantProgress()
  } catch (error) {
    window.__showErrToast?.('Не удалось обновить прогресс. Показаны сохранённые данные.')
  }

  const startApp = () => {
    document.getElementById('app').style.display = 'flex'
    if (participantLinked) document.getElementById('participant-link-banner')?.remove()
    else showParticipantLinkBanner()
    initI18n()
    window.showGlossaryTip = showGlossaryTip
    initHome()
    setCurrentWeek(U.currentWeek)
    initApp()
    renderTracker()

    initDiagnostic(() => {
      initHome()
      setCurrentWeek(U.currentWeek)
    })
    document.getElementById('btn-open-diag')?.addEventListener('click', openDiag)

    initReviewSheet(() => U.currentWeek, WEEKS)
    document.getElementById('btn-muhasaba')?.addEventListener('click', () =>
      openReviewSheet(U.currentWeek, WEEKS)
    )

    document.getElementById('btn-curator-report')?.addEventListener('click', () => {
      const level = U.level
      const LEVEL_OFFSET = { А: 0, Б: 6, В: 14, Г: 22 }
      const weekInLevel = level ? U.currentWeek - (LEVEL_OFFSET[level] ?? 0) : 0
      const allHabits = [...NAMAZ.map(n => n.id), ...DAILY.map(d => d.id)]
      const habitsDone = allHabits.filter(id => isChecked(id)).length
      let tasksDone = 0, tasksTotal = 0
      if (level && weekInLevel > 0 && PROGRAM_TASKS[level]) {
        const weekData = PROGRAM_TASKS[level][weekInLevel - 1]
        if (weekData) {
          const skill = U.skill || 'I'
          const tasks = weekData[skill] || weekData['I'] || []
          tasksTotal = tasks.length
          const done = lsGet(`ptasks_${level}_w${weekInLevel}_${U.skill}`, {})
          tasksDone = Object.values(done).filter(Boolean).length
        }
      }
      alert(`Отчёт: ${habitsDone}/${allHabits.length} привычек, ${tasksDone}/${tasksTotal} заданий, стрик ${U.streak} дней`)
    })

    window.addEventListener('iq:langchange', () => {
      initHome()
      renderTracker()
      rerenderCurrentScreen()
    })

    // Push notifications daily reminder
    initDailyReminder()

    track('app_open', { new_user: isNewUser })
  }

  if (isNewUser) {
    initOnboarding(startApp)
  } else {
    startApp()
  }
}

// ── AUTH BUTTON LISTENERS ─────────────────────────────────────────────────────

document.getElementById('btn-login')?.addEventListener('click', () => window.authLogin())
document.getElementById('btn-register')?.addEventListener('click', () => window.authRegister())
document.getElementById('btn-tg-login')?.addEventListener('click', () => window.authTelegram())
document.getElementById('link-to-register')?.addEventListener('click', e => { e.preventDefault(); window.showRegister() })
document.getElementById('link-to-login')?.addEventListener('click', e => { e.preventDefault(); window.showLogin() })

// ── BOOT ─────────────────────────────────────────────────────────────────────

const pendingTelegramSession = localStorage.getItem(TG_PENDING_SESSION_KEY)
if (pendingTelegramSession) {
  const errEl = document.getElementById('auth-err')
  if (errEl) errEl.textContent = 'Проверяем подтверждение Telegram…'
  completeTelegramLogin(pendingTelegramSession).catch(error => {
    localStorage.removeItem(TG_PENDING_SESSION_KEY)
    if (errEl) errEl.textContent = error.message || 'Не удалось войти через Telegram.'
  })
} else if (hasToken()) {
  api.me()
    .then(user => {
      localStorage.setItem('iq_user', JSON.stringify(user))
      enterApp()
    })
    .catch(() => {
      clearToken()
    })
}

async function refreshParticipantProgress() {
  if (!hasToken() || document.getElementById('app')?.style.display === 'none') return
  try {
    const changed = await syncParticipantProgress()
    if (!changed) return
    initHome()
    setCurrentWeek(U.currentWeek)
    renderTracker()
    rerenderCurrentScreen()
  } catch {}
}

window.addEventListener('focus', refreshParticipantProgress)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') refreshParticipantProgress()
})
