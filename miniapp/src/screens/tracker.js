import { NAMAZ, DAILY, WEEKLY, ONETIME } from '../data/habits.js'
import { haptic } from '../utils/tg.js'
import { lsGet, lsSet, todayKey } from '../utils/storage.js'

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
  document.getElementById('tp-sub').textContent = `${done} из ${total} выполнено`
  document.getElementById('tp-count').textContent = `${done}/${total}`
  document.getElementById('tp-bar').style.width = `${Math.round(done / total * 100)}%`
  document.getElementById('tracker-dot')?.classList.toggle('show', done < total)
}

export function renderTracker() {
  checked = lsGet('checked', {})

  const d = new Date()
  const months = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']
  const days = ['воскресенье','понедельник','вторник','среда','четверг','пятница','суббота']
  document.getElementById('tracker-date').textContent = `${d.getDate()} ${months[d.getMonth()]}, ${days[d.getDay()]}`

  renderWeekStrip()
  renderNamaz()
  renderDaily()
  renderWeeklyList()
  renderOnetimeList()
  updateProgress()
}

function renderWeekStrip() {
  const strip = document.getElementById('week-strip')
  strip.innerHTML = ''
  const DAYS = ['Вс','Пн','Вт','Ср','Чт','Пт','Сб']
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
