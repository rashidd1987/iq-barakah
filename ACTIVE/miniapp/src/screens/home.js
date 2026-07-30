import { getTgUser, tg } from '../utils/tg.js'
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

const PARTICIPANT_API_BASE = 'https://pwa-api.iq-barakah.ru'

export async function syncParticipantProgress() {
  const preview = new URLSearchParams(window.location.search).get('preview') === '1'
  if (preview || !tg?.initData) return false

  try {
    const response = await fetch(`${PARTICIPANT_API_BASE}/miniapp/participant`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data: tg.initData }),
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const participant = await response.json()
    const globalWeek = Number(participant.global_week)
    if (
      participant.found === false
      || !participant.level
      || !Number.isInteger(globalWeek)
      || globalWeek < 1
    ) {
      return false
    }

    U.level = participant.level
    U.currentWeek = globalWeek
    U.skill = ['I', 'II', 'III'].includes(participant.vakt_level)
      ? participant.vakt_level
      : 'I'

    // Keep the old offline fallback working if Telegram/API is temporarily unavailable.
    lsSet('level', U.level)
    lsSet('currentWeek', U.currentWeek)
    lsSet('skill', U.skill)
    return true
  } catch (error) {
    console.warn('Mini App progress sync unavailable:', error?.message || 'unknown error')
    return false
  }
}

export function initOnboarding() {
  if (lsGet('ob_done', false)) return
  const overlay = document.getElementById('ob-overlay')
  if (!overlay) return
  overlay.classList.remove('ob-hidden')

  let cur = 0
  const total = 4
  const slides = Array.from({ length: total }, (_, i) => document.getElementById(`ob-s${i}`))
  const dots = Array.from({ length: total }, (_, i) => document.getElementById(`ob-d${i}`))
  const nextBtn = document.getElementById('ob-next-btn')
  const skipBtn = document.getElementById('ob-skip-btn')

  function show(i) {
    slides.forEach((s, j) => s?.classList.toggle('active', j === i))
    dots.forEach((d, j) => d?.classList.toggle('active', j === i))
    nextBtn.textContent = i === total - 1 ? 'Начать программу 🌱' : 'Дальше →'
  }

  function finish() {
    lsSet('ob_done', true)
    overlay.classList.add('ob-hidden')
    setTimeout(() => overlay.remove(), 500)
  }

  nextBtn.onclick = () => {
    if (cur < total - 1) { cur++; show(cur) }
    else finish()
  }
  skipBtn.onclick = finish
}

export function initHome({ readPosition = true } = {}) {
  if (readPosition) readUrlParams()

  const tgUser = getTgUser()
  if (tgUser) {
    U.name = tgUser.first_name || 'Участник'
    const ava = document.getElementById('ava')
    if (ava) ava.textContent = (tgUser.first_name || 'У')[0].toUpperCase()
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

  // Streak banner (7+ дней)
  _renderStreakBanner()

  // Step progress bar
  _renderStepProgress()

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

function _renderStreakBanner() {
  const container = document.getElementById('streak-banner-slot')
  if (!container) return
  if (U.streak >= 7) {
    container.innerHTML = `
      <div class="streak-banner">
        <div class="streak-banner-icon">🔥</div>
        <div class="streak-banner-text">
          <div class="t">${U.streak} дней подряд — машааллах!</div>
          <div class="s">Продолжай — серия строит характер</div>
        </div>
      </div>`
  } else {
    container.innerHTML = ''
  }
}

function _renderStepProgress() {
  const container = document.getElementById('step-progress-slot')
  if (!container || !U.currentWeek) return
  const total = 30
  const done = Math.max(0, U.currentWeek - 1)
  const pct = Math.round(done / total * 100)
  container.innerHTML = `
    <div class="step-progress-bar">
      <div class="sp-icon">🗺️</div>
      <div class="sp-info">
        <div class="sp-title">Шаг ${U.currentWeek} из ${total}</div>
        <div class="sp-track"><div class="sp-fill" style="width:${pct}%"></div></div>
        <div class="sp-label">${done} шагов пройдено · ${total - done} осталось</div>
      </div>
      <div class="sp-pct">${pct}%</div>
    </div>`
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
