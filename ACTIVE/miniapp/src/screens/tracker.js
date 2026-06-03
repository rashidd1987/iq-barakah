import { NAMAZ, DAILY, WEEKLY, ONETIME } from '../data/habits.js'
import { PROGRAM_TASKS } from '../data/tasks.js'
import { haptic, sendData, cloudSet, openLink } from '../utils/tg.js'
import { lsGet, lsSet, todayKey } from '../utils/storage.js'
import { t, tf } from '../i18n.js'
import { U } from './home.js'

let checked = lsGet('checked', {})

function save() {
  lsSet('checked', checked)
  cloudSet('iq_checked', JSON.stringify(checked))
}

export function isChecked(id) { return !!(checked[todayKey()]?.[id]) }

function toggle(id) {
  const k = todayKey()
  if (!checked[k]) checked[k] = {}
  if (checked[k][id]) delete checked[k][id]
  else checked[k][id] = true
  save()
}

function toggleWeekly(id, bucket) {
  if (!checked[bucket]) checked[bucket] = {}
  if (checked[bucket][id]) delete checked[bucket][id]
  else checked[bucket][id] = true
  save()
}

export function updateProgress() {
  const all = [...NAMAZ.map(n => n.id), ...DAILY.map(d => d.id)]
  const total = all.length
  const done = all.filter(id => isChecked(id)).length
  document.getElementById('tp-sub').textContent = tf('doneOf', { done, total })
  document.getElementById('tp-count').textContent = `${done}/${total}`
  document.getElementById('tp-bar').style.width = `${Math.round(done / total * 100)}%`
  document.getElementById('tracker-dot')?.classList.toggle('show', done < total)
}

export function renderTracker() {
  checked = lsGet('checked', {})

  const d = new Date()
  try {
    const dateLocale = t('dateLocale')
    document.getElementById('tracker-date').textContent = d.toLocaleDateString(dateLocale, {
      day: 'numeric',
      month: 'long',
      weekday: 'long',
    })
  } catch(e) { console.error('[tracker] date error:', e.message) }

  renderMonthCal()
  _initCalToggle()
  renderWeekStrip()
  renderProgramTasks()
  renderNamaz()
  renderDaily()
  renderWeeklyList()
  renderOnetimeList()
  updateProgress()
}

// ── Month Calendar ────────────────────────────────────────────────────────────
let _calYear = new Date().getFullYear()
let _calMonth = new Date().getMonth()
let _calOpen = lsGet('mcal_open', true)

function _getDayStatus(dateStr) {
  const dayData = checked[dateStr]
  if (!dayData) return 'empty'
  const count = Object.keys(dayData).length
  if (count === 0) return 'empty'
  if (count >= 5) return 'full'
  return 'partial'
}

let _calToggleInited = false
function _initCalToggle() {
  const body = document.getElementById('mcal-body')
  const toggle = document.getElementById('mcal-toggle')
  if (!body || !toggle) return

  const apply = () => {
    body.style.display = _calOpen ? 'block' : 'none'
    toggle.textContent = _calOpen ? '▲' : '▼'
  }
  apply()

  if (_calToggleInited) return  // Add listeners only once!
  _calToggleInited = true

  const header = document.getElementById('mcal-title')
  const toggleEl = document.getElementById('mcal-toggle')

  const onToggle = () => {
    _calOpen = !_calOpen
    lsSet('mcal_open', _calOpen)
    apply()
  }
  header?.addEventListener('click', onToggle)
  toggleEl?.addEventListener('click', onToggle)
}

function renderMonthCal() {
  const cal = document.getElementById('month-cal')
  const title = document.getElementById('mcal-title')
  if (!cal) return

  const today = new Date()
  const y = _calYear, m = _calMonth
  const monthNames = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
  if (title) title.textContent = `${monthNames[m]} ${y}`

  const firstDay = new Date(y, m, 1)
  const lastDay = new Date(y, m + 1, 0)
  const startDow = (firstDay.getDay() + 6) % 7 // Mon=0

  let html = '<div class="mcal-grid">'
  // Day headers
  const days = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
  days.forEach(d => { html += `<div class="mcal-dow">${d}</div>` })
  // Empty cells before first day
  for (let i = 0; i < startDow; i++) html += '<div class="mcal-cell empty"></div>'
  // Days
  for (let day = 1; day <= lastDay.getDate(); day++) {
    const d = new Date(y, m, day)
    const dk = d.toISOString().split('T')[0]
    const isToday = dk === today.toISOString().split('T')[0]
    const status = _getDayStatus(dk)
    const isFuture = d > today
    html += `<div class="mcal-cell ${status}${isToday ? ' today' : ''}${isFuture ? ' future' : ''}">
      <span class="mcal-day">${day}</span>
      ${!isFuture && status !== 'empty' ? `<span class="mcal-dot ${status}"></span>` : ''}
    </div>`
  }
  html += '</div>'
  // Legend
  html += `<div class="mcal-legend">
    <span><span class="mcal-dot full"></span> Активный день</span>
    <span><span class="mcal-dot partial"></span> Частично</span>
  </div>`
  cal.innerHTML = html

  // Replace buttons with clones to remove stale listeners
  ;['mcal-prev', 'mcal-next'].forEach(id => {
    const old = document.getElementById(id)
    if (old) { const c = old.cloneNode(true); old.parentNode.replaceChild(c, old) }
  })
  document.getElementById('mcal-prev')?.addEventListener('click', () => {
    haptic()
    _calMonth--; if (_calMonth < 0) { _calMonth = 11; _calYear-- }
    renderMonthCal()
  })
  document.getElementById('mcal-next')?.addEventListener('click', () => {
    haptic()
    _calMonth++; if (_calMonth > 11) { _calMonth = 0; _calYear++ }
    renderMonthCal()
  })
}

function getProgramTasks() {
  const level = U.level
  if (!level || !PROGRAM_TASKS[level]) return null
  const LEVEL_OFFSET = { А: 0, Б: 6, В: 14, Г: 22 }
  const weekInLevel = U.currentWeek - (LEVEL_OFFSET[level] ?? 0)
  if (weekInLevel < 1) return null
  const weekData = PROGRAM_TASKS[level][weekInLevel - 1]
  if (!weekData) return null
  const skill = U.skill || 'I'
  return Array.isArray(weekData) ? weekData : (weekData[skill] || weekData['I'] || [])
}

function renderProgramTasks() {
  const tasks = getProgramTasks()
  const section = document.getElementById('program-tasks-section')
  const container = document.getElementById('program-tasks')
  if (!tasks || tasks.length === 0) {
    section.style.display = 'none'
    return
  }

  section.style.display = 'block'
  const level = U.level
  const LEVEL_OFFSET = { А: 0, Б: 6, В: 14, Г: 22 }
  const weekInLevel = U.currentWeek - (LEVEL_OFFSET[level] ?? 0)

  const storageKey = `ptasks_${level}_w${weekInLevel}_${U.skill}`
  const done = lsGet(storageKey, {})

  function _updatePtasksHeader() {
    const doneCount = Object.values(done).filter(Boolean).length
    const total = tasks.length
    const pct = total > 0 ? Math.round(doneCount / total * 100) : 0
    const subEl = document.getElementById('program-tasks-sub')
    const badgeEl = document.getElementById('program-tasks-badge')
    const pbarEl = document.getElementById('program-tasks-pbar')
    const labelEl = document.getElementById('program-tasks-label')
    if (labelEl) labelEl.textContent = `Задания · Уровень ${level} · Неделя ${weekInLevel}`
    if (subEl) subEl.textContent = `${doneCount} из ${total} выполнено`
    if (badgeEl) badgeEl.textContent = `${pct}%`
    if (pbarEl) pbarEl.style.width = `${pct}%`

    // Celebration banner when all done
    const existing = container.querySelector('.ptasks-all-done')
    if (doneCount === total && total > 0 && !existing) {
      haptic('success')
      const banner = document.createElement('div')
      banner.className = 'ptasks-all-done'
      banner.innerHTML = `
        <div class="ptasks-done-icon">🎉</div>
        <div>
          <div class="ptasks-done-text">Все задания выполнены! Альхамдулиллях</div>
          <div class="ptasks-done-sub">Ты молодец — продолжай в том же духе 💚</div>
        </div>`
      container.appendChild(banner)
    } else if (doneCount < total && existing) {
      existing.remove()
    }
  }

  container.innerHTML = ''
  tasks.forEach((taskText, idx) => {
    const isDone = !!done[idx]
    const el = document.createElement('div')
    el.className = `ptask-item${isDone ? ' ptask-done' : ''}`
    el.innerHTML = `
      <div class="ptask-cb${isDone ? ' done' : ''}"></div>
      <div class="ptask-text">${taskText}</div>`

    el.onclick = () => {
      haptic()
      const nowDone = !done[idx]
      if (nowDone) done[idx] = true
      else delete done[idx]
      lsSet(storageKey, done)

      el.classList.toggle('ptask-done', nowDone)
      const cb = el.querySelector('.ptask-cb')
      cb.classList.toggle('done', nowDone)
      el.classList.add('pop')
      setTimeout(() => el.classList.remove('pop'), 350)

      _updatePtasksHeader()
    }
    container.appendChild(el)
  })

  _updatePtasksHeader()

  // Calendar button
  const existing = container.parentElement.querySelector('.ptasks-cal-btn')
  if (!existing) {
    const calBtn = document.createElement('button')
    calBtn.className = 'ptasks-cal-btn'
    calBtn.innerHTML = '📅 Добавить в календарь (все 7 дней)'
    calBtn.onclick = () => { haptic(); _addWeekToCalendar(level, weekInLevel, tasks) }
    container.parentElement.appendChild(calBtn)
  }
}

// ── Calendar export (ICS) ─────────────────────────────────────────────────────
function _addWeekToCalendar(level, weekInLevel, tasks) {
  const LEVEL_OFFSET = { А: 0, Б: 6, В: 14, Г: 22 }
  const globalWeek = (LEVEL_OFFSET[level] ?? 0) + weekInLevel

  const today = new Date()
  const dow = today.getDay()
  const monday = new Date(today)
  monday.setDate(today.getDate() - ((dow + 6) % 7))

  const pad = n => String(n).padStart(2, '0')
  const fmt = d => `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}T${pad(d.getHours())}${pad(d.getMinutes())}00`

  const taskLines = tasks.map((t, i) =>
    `${i+1}. ${t.replace(/[\r\n,;]/g, ' ').substring(0, 120)}`
  ).join('\\n')

  const summary = `IQ Barakah · Неделя ${globalWeek} · Уровень ${level}`
  const desc = `Задания на каждый день:\\n${taskLines}\\n\\nОтмечай выполненное в Трекере`

  const CRLF = '\r\n'
  let vevents = ''
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    d.setHours(9, 0, 0, 0)
    const dEnd = new Date(d)
    dEnd.setHours(9, 30, 0, 0)
    const uid = `iqb-w${globalWeek}-d${i+1}-${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}@iqbarakah`
    vevents += `BEGIN:VEVENT${CRLF}UID:${uid}${CRLF}DTSTART:${fmt(d)}${CRLF}DTEND:${fmt(dEnd)}${CRLF}SUMMARY:${summary}${CRLF}DESCRIPTION:${desc}${CRLF}END:VEVENT${CRLF}`
  }

  // Google Calendar URL (HTTPS — works in Telegram WebApp on all platforms)
  monday.setHours(9, 0, 0, 0)
  const mondayEnd = new Date(monday); mondayEnd.setHours(9, 30, 0, 0)
  const title = encodeURIComponent(`IQ Barakah · Неделя ${globalWeek} · Уровень ${level}`)
  const details = encodeURIComponent(`Задания на каждый день недели:\n${tasks.slice(0,5).map((t,i)=>`${i+1}. ${t.substring(0,100)}`).join('\n')}\n\nОтмечай выполненное в Трекере`)
  const recur = 'RRULE%3AFREQ%3DDAILY%3BCOUNT%3D7'
  const fmtG = d => `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}T${pad(d.getHours())}${pad(d.getMinutes())}00`
  openLink(`https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&dates=${fmtG(monday)}/${fmtG(mondayEnd)}&recur=${recur}&details=${details}&sf=true&output=xml`)
}

// ── Individual habit streak ───────────────────────────────────────────────────
function getHabitStreak(id) {
  const today = new Date()
  let streak = 0
  for (let i = 0; i < 365; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const key = d.toISOString().split('T')[0]
    if (checked[key]?.[id]) {
      streak++
    } else {
      if (i === 0) continue // today not yet done — don't break streak
      break
    }
  }
  return streak
}

function streakBadge(id) {
  const s = getHabitStreak(id)
  if (s < 2) return ''
  const color = s >= 7 ? '#e74c3c' : s >= 3 ? '#e67e22' : '#f39c12'
  return `<div class="habit-streak-badge" style="background:${color}">🔥${s}</div>`
}

function renderWeekStrip() {
  const strip = document.getElementById('week-strip')
  strip.innerHTML = ''
  const DAYS = t('weekdaysShort')
  const today = new Date()
  const dow = today.getDay()
  const monday = new Date(today)
  monday.setDate(today.getDate() - ((dow + 6) % 7))

  for (let i = 0; i < 7; i++) {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    const isToday = d.toDateString() === today.toDateString()
    const dk = d.toISOString().split('T')[0]
    const hasDone = checked[dk] && Object.keys(checked[dk]).length > 0
    const chip = document.createElement('div')
    chip.className = `day-chip${isToday ? ' today' : hasDone ? ' done-day' : ''}`
    chip.innerHTML = `<span class="dn">${DAYS[d.getDay()]}</span><span class="dd">${d.getDate()}</span><span class="dc"></span>`
    strip.appendChild(chip)
    if (isToday) setTimeout(() => chip.scrollIntoView({ inline: 'center', block: 'nearest' }), 100)
  }
}

function renderNamaz() {
  const ng = document.getElementById('namaz-grid')
  ng.innerHTML = ''
  NAMAZ.forEach(n => {
    const done = isChecked(n.id)
    const s = getHabitStreak(n.id)
    const btn = document.createElement('button')
    btn.className = `namaz-btn${done ? ' done' : ''}`
    btn.innerHTML = `
      <span class="nl">${n.label}</span>
      <span class="ni">${done ? '✅' : n.icon}</span>
      ${s >= 2 ? `<span class="namaz-streak">🔥${s}</span>` : ''}`
    btn.onclick = () => {
      haptic()
      toggle(n.id)
      const d = isChecked(n.id)
      const s2 = getHabitStreak(n.id)
      btn.className = `namaz-btn${d ? ' done' : ''}`
      btn.innerHTML = `
        <span class="nl">${n.label}</span>
        <span class="ni">${d ? '✅' : n.icon}</span>
        ${s2 >= 2 ? `<span class="namaz-streak">🔥${s2}</span>` : ''}`
      updateProgress()
    }
    ng.appendChild(btn)
  })
}

function renderDaily() {
  const dh = document.getElementById('daily-habits')
  dh.innerHTML = ''
  DAILY.forEach(h => {
    const el = document.createElement('div')
    const done = isChecked(h.id)
    const s = getHabitStreak(h.id)
    el.className = `habit-item${done ? ' checked' : ''}`
    el.innerHTML = `
      <div class="hcheck">${done ? '<span style="color:white;font-size:14px;">✓</span>' : ''}</div>
      <div class="act-ic gr" style="width:38px;height:38px;border-radius:10px;font-size:18px;">${h.icon}</div>
      <div class="habit-info"><div class="t">${h.label}</div><div class="s">${h.sub}</div></div>
      ${s >= 1 ? `<div class="habit-streak ${s >= 7 ? 'hot' : s >= 3 ? 'warm' : ''}">🔥${s}</div>` : '<div class="habit-streak muted">○</div>'}`
    el.onclick = () => {
      haptic()
      toggle(h.id)
      const d = isChecked(h.id)
      el.classList.toggle('checked', d)
      el.querySelector('.hcheck').innerHTML = d ? '<span style="color:white;font-size:14px;">✓</span>' : ''
      el.classList.add('pop')
      setTimeout(() => el.classList.remove('pop'), 350)
      // Update streak display
      const s2 = getHabitStreak(h.id)
      const sd = el.querySelector('.habit-streak')
      if (sd) {
        sd.className = `habit-streak ${s2 >= 7 ? 'hot' : s2 >= 3 ? 'warm' : s2 >= 1 ? '' : 'muted'}`
        sd.textContent = s2 >= 1 ? `🔥${s2}` : '○'
      }
      updateProgress()
    }
    dh.appendChild(el)
  })
}

function makeWeeklyItem(w, bucket) {
  const done = !!(checked[bucket]?.[w.id])
  const el = document.createElement('div')
  el.className = `weekly-item${done ? ' done-w' : ''}`
  el.innerHTML = `
    <div class="wi-icon">${w.icon}</div>
    <div class="wi-info"><div class="t">${w.label}</div><div class="s">${w.sub}</div></div>
    <div class="wi-check">${done ? '<span style="font-size:13px;color:white;">✓</span>' : ''}</div>`
  el.onclick = () => {
    haptic()
    toggleWeekly(w.id, bucket)
    const d = !!(checked[bucket]?.[w.id])
    el.classList.toggle('done-w', d)
    el.querySelector('.wi-check').innerHTML = d ? '<span style="font-size:13px;color:white;">✓</span>' : ''
  }
  return el
}

function renderWeeklyList() {
  const wh = document.getElementById('weekly-habits')
  wh.innerHTML = ''
  WEEKLY.forEach(w => wh.appendChild(makeWeeklyItem(w, 'weekly')))
}

function renderOnetimeList() {
  const oh = document.getElementById('onetime-habits')
  oh.innerHTML = ''
  ONETIME.forEach(w => oh.appendChild(makeWeeklyItem(w, 'onetime')))
}

export function getTrackerPayload() {
  return { action: 'save_tracker', habits: checked }
}
