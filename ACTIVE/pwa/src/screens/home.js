import { getTgUser } from '../utils/tg.js'
import { WEEKS, LEVEL_OFFSET, LEVEL_ICONS, LEVEL_LABELS } from '../data/weeks.js'
import { lsGet, lsSet } from '../utils/storage.js'
import { computeAllStats } from '../utils/stats.js'
import { t } from '../i18n.js'

export const U = {
  name: 'Участник',
  level: '',
  currentWeek: 0,
  skill: 'I',   // I / II / III — уровень навыка участника
  streak: 0,
  deeds: 0,
  xp: 0,
}

export function initHome() {
  readUrlParams()

  const tgUser = getTgUser()
  if (tgUser) {
    U.name = tgUser.first_name || tgUser.name || 'Участник'
  }
  // PWA: берём имя из localStorage (сохраняется при логине)
  try {
    const savedUser = JSON.parse(localStorage.getItem('iq_user') || '{}')
    if (savedUser.name) U.name = savedUser.name.split(' ')[0]
  } catch {}
  const ava = document.getElementById('ava')
  if (ava) {
    ava.textContent = U.name[0].toUpperCase()
    ava.onclick = () => _showProfileMenu()
  }

  // Curator preview banner
  const previewBanner = document.getElementById('preview-banner')
  if (previewBanner) {
    previewBanner.style.display = U.previewMode ? 'flex' : 'none'
  }

  // Greeting
  const h = new Date().getHours()
  const greets = ['Ас-саляму алейкум', t('goodMorning'), t('goodDay'), t('goodEvening'), t('goodNight')]
  const gi = h < 5 ? 4 : h < 12 ? 1 : h < 17 ? 2 : h < 22 ? 3 : 4
  const greetEl = document.getElementById('greet')
  if (greetEl) greetEl.textContent = greets[gi] + ' 👋'

  const subEl = document.getElementById('uname-sub')
  if (subEl) subEl.textContent = U.name + (U.level ? ' · ' + (LEVEL_LABELS[U.level] || U.level) : '')

  const pillEl = document.getElementById('lvl-pill')
  if (pillEl) pillEl.textContent = U.level
    ? (LEVEL_ICONS[U.level] || '🌱') + ' ' + (LEVEL_LABELS[U.level] || U.level)
    : '🌱 IQ Barakah'

  // Stats — вычисляем из реальных данных localStorage
  const weeksDone = U.currentWeek > 0 ? Math.max(0, U.currentWeek - 1) : 0
  const stats = computeAllStats(U.level, weeksDone)
  U.streak = stats.streak
  U.deeds  = stats.deeds
  U.xp     = stats.xp

  document.getElementById('sv-streak').textContent = U.streak
  document.getElementById('sv-weeks').textContent  = weeksDone
  document.getElementById('sv-deeds').textContent  = U.deeds
  document.getElementById('sv-xp').textContent     = U.xp

  // Streak fire animation
  const streakEl = document.getElementById('sv-streak')
  if (U.streak >= 7) streakEl.classList.add('streak-hot')
  else streakEl.classList.remove('streak-hot')

  // 7-day streak dots
  _renderStreakWeek()

  // Ring progress
  const pct = U.currentWeek > 0 ? Math.round(Math.max(0, U.currentWeek - 1) / 30 * 100) : 0
  document.getElementById('rpct').textContent = pct + '%'
  const circ = 2 * Math.PI * 62
  document.getElementById('ring')?.setAttribute('stroke-dashoffset', (circ * (1 - pct / 100)).toFixed(1))

  // Current week banner
  if (U.currentWeek > 0 && U.currentWeek <= WEEKS.length) {
    const cw = WEEKS[U.currentWeek - 1]
    if (cw) {
      document.getElementById('cw-icon').textContent  = cw.icon
      document.getElementById('cw-title').textContent = cw.num + ' · ' + cw.title
      document.getElementById('cw-sub').textContent   = cw.sub + ' · ' + t('active')
      document.getElementById('act-cur-week').textContent = cw.num + ' · ' + cw.title
    }
  } else {
    document.getElementById('cw-title').textContent = 'Пройдите диагностику'
    document.getElementById('cw-sub').textContent   = 'Нажмите чтобы определить свой уровень →'
  }
}

function _renderStreakWeek() {
  const el = document.getElementById('streak-week')
  if (!el) return

  const checked = lsGet('checked', {})
  const today = new Date()
  const DAYS_RU = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']

  let html = ''
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const key = d.toISOString().split('T')[0]
    const isToday = i === 0
    const hasDone = checked[key] && Object.keys(checked[key]).length > 0

    // Count how many habits done for fill %
    const dayHabits = checked[key] ? Object.keys(checked[key]).length : 0
    const full = dayHabits >= 5  // 5+ привычек = полный день
    const partial = dayHabits >= 1 && dayHabits < 5

    const cls = isToday ? 'sw-dot today' : full ? 'sw-dot full' : partial ? 'sw-dot partial' : 'sw-dot empty'
    html += `
      <div class="${cls}">
        <div class="sw-icon">${full ? '✅' : partial ? '🟡' : isToday ? '📍' : '⬜'}</div>
        <div class="sw-day">${DAYS_RU[d.getDay()]}</div>
      </div>`
  }
  el.innerHTML = html
}

function readUrlParams() {
  const p = new URLSearchParams(window.location.search)
  const lvl   = p.get('lvl') || ''
  const wk    = parseInt(p.get('wk') || '0', 10)
  const skill = p.get('skill') || 'I'
  const preview = p.get('preview') === '1'

  // Curator preview mode: unlock all lessons without saving to localStorage
  if (preview) {
    U.level = lvl || lsGet('level', 'А') || 'А'
    U.currentWeek = 31  // > 30 = all unlocked
    U.skill = skill
    U.previewMode = true
    return
  }

  if (lvl && wk > 0 && lvl in LEVEL_OFFSET) {
    U.level = lvl
    U.currentWeek = LEVEL_OFFSET[lvl] + wk
    // Save to localStorage so next opens without params still work
    lsSet('level', lvl)
    lsSet('currentWeek', U.currentWeek)
    lsSet('skill', skill)
  }
  U.skill = ['I', 'II', 'III'].includes(skill) ? skill : 'I'

  // Fallback to localStorage
  if (!U.level) {
    U.level = lsGet('level', '')
    const savedWeek = lsGet('currentWeek', 0)
    if (savedWeek > 0) U.currentWeek = savedWeek
    const savedSkill = lsGet('skill', 'I')
    if (['I','II','III'].includes(savedSkill)) U.skill = savedSkill
  }
}

function _showProfileMenu() {
  let savedUser = {}
  try { savedUser = JSON.parse(localStorage.getItem('iq_user') || '{}') } catch {}
  const name  = savedUser.name  || U.name || 'Участник'
  const email = savedUser.email || ''
  const remTime = localStorage.getItem('iq_remind_time') || '20:00'
  const pushGranted = 'Notification' in window && Notification.permission === 'granted'

  const html = `
    <div style="text-align:center;padding:8px 0 20px">
      <div style="width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#2c5f2d,#3d7a3e);display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:800;color:white;margin:0 auto 10px">${name[0].toUpperCase()}</div>
      <div style="font-size:18px;font-weight:800;color:var(--text)">${name}</div>
      ${email ? `<div style="font-size:13px;color:var(--muted);margin-top:3px">${email}</div>` : ''}
    </div>
    <div style="display:flex;flex-direction:column;gap:0">
      <div class="settings-row">
        <span>👑 Подписка Premium</span>
        <button class="btn btn-p" style="padding:8px 14px;font-size:13px" onclick="closeSheet();openPaywall()">Подключить</button>
      </div>
      <div class="settings-row">
        <span>🔔 Напоминание</span>
        <input type="time" value="${remTime}" onchange="localStorage.setItem('iq_remind_time',this.value)" style="width:90px"/>
      </div>
      ${!pushGranted ? `
      <div class="settings-row">
        <span>📲 Уведомления</span>
        <button class="btn btn-o" style="padding:8px 14px;font-size:13px" onclick="_pwaPushAsk()">Включить</button>
      </div>` : ''}
      <div class="settings-row">
        <span>📥 Экспорт данных</span>
        <button class="btn btn-o" style="padding:8px 14px;font-size:13px" onclick="closeSheet();_pwaExport()">Скачать</button>
      </div>
      <div class="settings-row" style="border:none;margin-top:8px">
        <button class="btn" onclick="_pwaLogout()" style="width:100%;background:#fef2f2;color:#dc2626;border:1.5px solid #fecaca">🚪 Выйти из аккаунта</button>
      </div>
    </div>
  `
  window.openSheet(html)
}

window._pwaLogout = function() {
  localStorage.removeItem('iq_token')
  localStorage.removeItem('iq_user')
  window.location.reload()
}

window._pwaPushAsk = async function() {
  const { requestPushPermission } = await import('../push.js')
  const result = await requestPushPermission()
  if (result === 'granted') {
    const { initDailyReminder } = await import('../push.js')
    initDailyReminder()
    closeSheet()
    setTimeout(() => window.openSheet('<div style="text-align:center;padding:24px"><div style="font-size:48px;margin-bottom:12px">🔔</div><div style="font-size:18px;font-weight:800">Уведомления включены!</div><p style="color:var(--muted);margin-top:8px">Напомним каждый день в 20:00</p></div>'), 300)
  }
}

window._pwaExport = function() {
  import('../export.js').then(m => m.exportProgress())
}
