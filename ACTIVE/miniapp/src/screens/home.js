import { getTgUser } from '../utils/tg.js'
import { WEEKS, LEVEL_OFFSET, LEVEL_ICONS, LEVEL_LABELS } from '../data/weeks.js'
import { lsGet } from '../utils/storage.js'
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
    U.name = tgUser.first_name || 'Участник'
    const ava = document.getElementById('ava')
    if (ava) ava.textContent = (tgUser.first_name || 'У')[0].toUpperCase()
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
    document.getElementById('cw-title').textContent = t('programNotStarted')
    document.getElementById('cw-sub').textContent   = t('openBotStart')
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

  if (lvl && wk > 0 && lvl in LEVEL_OFFSET) {
    U.level = lvl
    U.currentWeek = LEVEL_OFFSET[lvl] + wk
  }
  U.skill = ['I', 'II', 'III'].includes(skill) ? skill : 'I'

  // Fallback to localStorage
  if (!U.level) U.level = lsGet('level', '')
}
