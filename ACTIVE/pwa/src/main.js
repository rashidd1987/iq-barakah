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
    enterApp()
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
    enterApp(true) // new user → show onboarding
  } catch (e) {
    errEl.textContent = e.message
  } finally {
    btnTxt.style.display = ''; spin.style.display = 'none'
  }
}

window.authTelegram = function() {
  alert('Войти через Telegram: нажмите «Зарегистрироваться», войдите через email. Привязка Telegram будет в следующем обновлении.')
}

// ── APP INIT ─────────────────────────────────────────────────────────────────

function enterApp(isNewUser = false) {
  document.getElementById('auth-screen').classList.add('hidden')

  const startApp = () => {
    document.getElementById('app').style.display = 'flex'
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

if (hasToken()) {
  api.me()
    .then(user => {
      localStorage.setItem('iq_user', JSON.stringify(user))
      enterApp()
    })
    .catch(() => {
      clearToken()
    })
}
