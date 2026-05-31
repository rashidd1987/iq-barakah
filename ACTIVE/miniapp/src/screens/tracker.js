import { NAMAZ, DAILY, WEEKLY, ONETIME } from '../data/habits.js'
import { PROGRAM_TASKS } from '../data/tasks.js'
import { haptic, sendData } from '../utils/tg.js'
import { lsGet, lsSet, todayKey } from '../utils/storage.js'
import { t, tf } from '../i18n.js'
import { U } from './home.js'

let checked = lsGet('checked', {})

function save() { lsSet('checked', checked) }

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
  document.getElementById('tracker-date').textContent = d.toLocaleDateString(t('dateLocale'), {
    day: 'numeric',
    month: 'long',
    weekday: 'long',
  })

  renderWeekStrip()
  renderProgramTasks()
  renderNamaz()
  renderDaily()
  renderWeeklyList()
  renderOnetimeList()
  updateProgress()
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
  const label = document.getElementById('program-tasks-label')
  if (!tasks || tasks.length === 0) {
    section.style.display = 'none'
    return
  }

  section.style.display = 'block'
  const level = U.level
  const LEVEL_OFFSET = { А: 0, Б: 6, В: 14, Г: 22 }
  const weekInLevel = U.currentWeek - (LEVEL_OFFSET[level] ?? 0)
  label.textContent = `📋 Задания · Уровень ${level} · Неделя ${weekInLevel}`

  const storageKey = `ptasks_${level}_w${weekInLevel}_${U.skill}`
  const done = lsGet(storageKey, {})

  container.innerHTML = ''
  tasks.forEach((taskText, idx) => {
    const isDone = !!done[idx]
    const el = document.createElement('div')
    el.className = `habit-item${isDone ? ' checked' : ''}`
    el.innerHTML = `
      <div class="hcheck">${isDone ? '<span style="color:white;font-size:14px;">✓</span>' : ''}</div>
      <div class="habit-info" style="flex:1"><div class="t" style="white-space:pre-wrap;line-height:1.4;">${taskText}</div></div>`

    el.onclick = () => {
      haptic()
      const nowDone = !done[idx]
      if (nowDone) done[idx] = true
      else delete done[idx]
      lsSet(storageKey, done)

      el.classList.toggle('checked', nowDone)
      el.querySelector('.hcheck').innerHTML = nowDone ? '<span style="color:white;font-size:14px;">✓</span>' : ''
      el.classList.add('pop')
      setTimeout(() => el.classList.remove('pop'), 350)

      sendData({
        action: 'check_task',
        level,
        week: weekInLevel,
        task_index: idx,
        checked: nowDone,
        total_tasks: tasks.length,
      })
    }
    container.appendChild(el)
  })
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
    const btn = document.createElement('button')
    btn.className = `namaz-btn${done ? ' done' : ''}`
    btn.innerHTML = `<span class="nl">${n.label}</span><span class="ni">${done ? '✅' : n.icon}</span>`
    btn.onclick = () => {
      haptic()
      toggle(n.id)
      const d = isChecked(n.id)
      btn.className = `namaz-btn${d ? ' done' : ''}`
      btn.innerHTML = `<span class="nl">${n.label}</span><span class="ni">${d ? '✅' : n.icon}</span>`
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
    el.className = `habit-item${done ? ' checked' : ''}`
    el.innerHTML = `
      <div class="hcheck">${done ? '<span style="color:white;font-size:14px;">✓</span>' : ''}</div>
      <div class="act-ic gr" style="width:38px;height:38px;border-radius:10px;font-size:18px;">${h.icon}</div>
      <div class="habit-info"><div class="t">${h.label}</div><div class="s">${h.sub}</div></div>
      <div class="habit-streak">🔥${h.streak}</div>`
    el.onclick = () => {
      haptic()
      toggle(h.id)
      const d = isChecked(h.id)
      el.classList.toggle('checked', d)
      el.querySelector('.hcheck').innerHTML = d ? '<span style="color:white;font-size:14px;">✓</span>' : ''
      el.classList.add('pop')
      setTimeout(() => el.classList.remove('pop'), 350)
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
