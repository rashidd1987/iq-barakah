import { addToHomeScreen, checkHomeScreenStatus, haptic, sendData, tg } from '../utils/tg.js'
import { lsGet, lsSet } from '../utils/storage.js'

export function openSheet(id) {
  document.getElementById(`ov-${id}`)?.classList.add('open')
  document.getElementById(`sh-${id}`)?.classList.add('open')
}

export function closeSheet(id) {
  document.getElementById(`ov-${id}`)?.classList.remove('open')
  document.getElementById(`sh-${id}`)?.classList.remove('open')
}

// ── Glossary popup ──────────────────────────────────────────────────────────
export function showGlossaryTip(term) {
  const entry = (typeof GLOSSARY !== 'undefined') ? GLOSSARY[term] : null
  if (!entry) return

  let popup = document.getElementById('glossary-popup')
  if (!popup) {
    popup = document.createElement('div')
    popup.id = 'glossary-popup'
    popup.className = 'glossary-popup'
    popup.onclick = () => popup.classList.remove('show')
    document.body.appendChild(popup)
  }

  popup.innerHTML = `
    <div class="gp-term">${term} <span class="gp-ar">${entry.ar}</span></div>
    <div class="gp-text">${entry.text}</div>
    <div class="gp-close">✕ закрыть</div>`
  popup.classList.add('show')
}

export function showToast(msg) {
  let t = document.getElementById('toast')
  if (!t) {
    t = document.createElement('div')
    t.id = 'toast'
    t.style.cssText = 'position:fixed;bottom:90px;left:50%;transform:translateX(-50%) translateY(20px);background:#1a3d1b;color:white;padding:10px 20px;border-radius:20px;font-size:14px;font-weight:600;z-index:200;opacity:0;transition:all .25s ease;white-space:nowrap;max-width:90vw;text-align:center;'
    document.body.appendChild(t)
  }
  t.textContent = msg
  requestAnimationFrame(() => {
    t.style.opacity = '1'; t.style.transform = 'translateX(-50%) translateY(0)'
    setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(-50%) translateY(20px)' }, 2200)
  })
}

// ── Telegram home-screen shortcut ──────────────────────────────────────────
const HOME_HINT_DISMISSED_KEY = 'home_shortcut_hint_dismissed'

export function initHomeScreenShortcut(completedSteps = 0) {
  const avatar = document.getElementById('ava')
  const installButton = document.getElementById('btn-add-home-screen')
  const closeButton = document.getElementById('btn-close-profile')
  const overlay = document.getElementById('ov-profile')

  const openProfile = () => {
    haptic()
    openSheet('profile')
    refreshHomeScreenStatus()
  }

  avatar?.addEventListener('click', openProfile)
  closeButton?.addEventListener('click', () => closeSheet('profile'))
  overlay?.addEventListener('click', () => closeSheet('profile'))
  installButton?.addEventListener('click', requestHomeScreenShortcut)

  tg?.onEvent?.('homeScreenAdded', () => {
    lsSet(HOME_HINT_DISMISSED_KEY, true)
    document.getElementById('home-shortcut-slot')?.replaceChildren()
    closeSheet('profile')
    showToast('Иконка IQ Barakah добавлена')
  })

  // Show once after three completed steps. The avatar option remains available.
  if (completedSteps >= 3 && !lsGet(HOME_HINT_DISMISSED_KEY, false)) {
    checkHomeScreenStatus((status) => {
      if (status === 'added' || status === 'unsupported') return
      renderHomeScreenHint()
    })
  }
}

function refreshHomeScreenStatus() {
  const button = document.getElementById('btn-add-home-screen')
  const statusText = document.getElementById('home-screen-status')
  if (!button || !statusText) return

  checkHomeScreenStatus((status) => {
    if (status === 'added') {
      button.disabled = true
      button.querySelector('.profile-action-title').textContent = 'Уже на главном экране'
      statusText.textContent = 'Иконка IQ Barakah уже добавлена на телефон'
      return
    }
    if (status === 'unsupported') {
      button.disabled = true
      button.querySelector('.profile-action-title').textContent = 'Недоступно на этом устройстве'
      statusText.textContent = 'Обновите Telegram на телефоне и откройте мини-приложение снова'
      return
    }
    button.disabled = false
    button.querySelector('.profile-action-title').textContent = 'Добавить на главный экран'
    statusText.textContent = 'IQ Barakah будет открываться отдельной иконкой через Telegram'
  })
}

function requestHomeScreenShortcut() {
  haptic()
  if (!addToHomeScreen()) {
    showToast('Обновите Telegram, чтобы добавить иконку')
    return
  }
  lsSet(HOME_HINT_DISMISSED_KEY, true)
}

function renderHomeScreenHint() {
  const slot = document.getElementById('home-shortcut-slot')
  if (!slot) return

  slot.innerHTML = `
    <div class="home-shortcut-hint">
      <button class="home-shortcut-dismiss" type="button" aria-label="Закрыть">×</button>
      <div class="home-shortcut-icon">📲</div>
      <div class="home-shortcut-copy">
        <div class="home-shortcut-title">IQ Barakah всегда под рукой</div>
        <div class="home-shortcut-sub">Добавьте мини-приложение отдельной иконкой на телефон</div>
      </div>
      <button class="home-shortcut-add" type="button">Добавить</button>
    </div>`

  slot.querySelector('.home-shortcut-add')?.addEventListener('click', requestHomeScreenShortcut)
  slot.querySelector('.home-shortcut-dismiss')?.addEventListener('click', () => {
    lsSet(HOME_HINT_DISMISSED_KEY, true)
    slot.innerHTML = ''
  })

}

// ── Review sheet state ──
let rEmoji = null, rTask = null, rUseful = null

export function initReviewSheet(getCurrentWeek, weeksData) {
  // Emoji buttons
  document.querySelectorAll('.em-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      haptic()
      document.querySelectorAll('.em-btn').forEach(b => b.classList.remove('sel'))
      btn.classList.add('sel')
      rEmoji = btn.dataset.emoji
    })
  })

  // Rating rows
  ;['rt-task', 'rt-useful'].forEach(id => {
    const row = document.getElementById(id)
    if (!row) return
    ;[1, 2, 3, 4, 5].forEach(n => {
      const b = document.createElement('button')
      b.className = 'rb'; b.textContent = n
      b.addEventListener('click', () => {
        haptic()
        row.querySelectorAll('.rb').forEach(x => x.classList.remove('sel'))
        b.classList.add('sel')
        if (id === 'rt-task') rTask = n; else rUseful = n
      })
      row.appendChild(b)
    })
  })

  // Submit
  document.getElementById('rv-btn')?.addEventListener('click', () => {
    const text = document.getElementById('rv-text')?.value?.trim()
    if (!rEmoji || !rTask || !text) {
      haptic('error')
      showToast('Выберите настроение, оценку и напишите отзыв')
      return
    }
    const btn = document.getElementById('rv-btn')
    btn.innerHTML = '<div class="spin"></div> Отправляем...'
    btn.disabled = true
    setTimeout(() => {
      haptic('success')
      document.getElementById('rv-form').style.display = 'none'
      document.getElementById('rv-ok').classList.add('show')
      sendData({ type: 'review', week: getCurrentWeek(), emoji: rEmoji, task: rTask, useful: rUseful, text })
    }, 1100)
  })

  // OK button
  document.getElementById('rv-ok-btn')?.addEventListener('click', () => {
    closeSheet('review')
    import('../app.js').then(m => m.switchScreen('lessons'))
  })

  // Overlay click to close
  document.getElementById('ov-lesson')?.addEventListener('click', () => closeSheet('lesson'))
  document.getElementById('ov-review')?.addEventListener('click', () => closeSheet('review'))
}

export function openReviewSheet(currentWeek, weeksData) {
  haptic()
  const lbl = document.getElementById('rv-week-lbl')
  if (lbl && currentWeek > 0 && currentWeek <= weeksData.length) {
    const cw = weeksData[currentWeek - 1]
    if (cw) lbl.textContent = `${cw.num} · ${cw.title} · Три вопроса`
  }
  openSheet('review')
}
