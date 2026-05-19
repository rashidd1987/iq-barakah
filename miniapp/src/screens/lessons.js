import { WEEKS, PHASE_LABELS, WEEK_CONTENT } from '../data/weeks.js'
import { haptic } from '../utils/tg.js'
import { openSheet } from '../components/sheets.js'

export let currentWeek = 0

export function setCurrentWeek(w) { currentWeek = w }

export function renderLessons(phase = 'all') {
  const list = document.getElementById('week-list')
  list.innerHTML = ''

  const filtered = phase === 'all' ? WEEKS : WEEKS.filter(w => w.phase === phase)
  let lastPhase = null
  let curEl = null

  filtered.forEach(w => {
    const wi = WEEKS.indexOf(w) + 1

    if (w.phase !== lastPhase) {
      const l = document.createElement('div')
      l.className = 'phase-lbl'
      l.textContent = PHASE_LABELS[w.phase]
      list.appendChild(l)
      lastPhase = w.phase
    }

    const hasCur = currentWeek > 0
    const done   = hasCur ? wi < currentWeek : false
    const isCur  = hasCur ? wi === currentWeek : false
    const locked = hasCur ? wi > currentWeek : (wi > 1)

    const el = document.createElement('div')
    el.className = `week-item${isCur ? ' week-item-current' : ''}`
    el.innerHTML = `
      <div class="wnum ${locked ? 'lock' : done ? 'done' : 'cur'}">${w.num}</div>
      <div class="winfo"><div class="t">${w.icon} ${w.title}</div><div class="s">${w.sub}</div></div>
      <div class="wstat">${locked ? '🔒' : done ? '✅' : '📖'}</div>`
    el.onclick = () => openLessonSheet(w, done, isCur, locked)
    list.appendChild(el)
    if (isCur) curEl = el
  })

  if (curEl) setTimeout(() => curEl.scrollIntoView({ behavior: 'smooth', block: 'center' }), 120)

  // Sync progress bar
  const pct = currentWeek > 0 ? Math.round(Math.max(0, currentWeek - 1) / 30 * 100) : 0
  const bar = document.getElementById('lessons-pbar')
  if (bar) bar.style.width = pct + '%'
}

function openLessonSheet(w, done, isCur, locked) {
  haptic()
  document.getElementById('sl-icon').textContent = w.icon
  document.getElementById('sl-title').textContent = w.title
  document.getElementById('sl-sub').textContent = `${w.sub} · ${locked ? '🔒 Заблокировано' : done ? '✅ Завершена' : '📖 Текущая'}`

  const c = WEEK_CONTENT[w.phase] || WEEK_CONTENT.s1
  const rows = document.getElementById('sl-rows')
  rows.innerHTML = locked
    ? `<div class="s-row"><div class="s-ri">🔒</div><div class="s-rt"><div class="l">Как открыть</div><div class="v">Сдайте мухасабу за текущую неделю — куратор откроет следующую</div></div></div>`
    : `<div class="s-row"><div class="s-ri">📿</div><div class="s-rt"><div class="l">Азкар недели</div><div class="v">${c.az}</div></div></div>
       <div class="s-row"><div class="s-ri">📖</div><div class="s-rt"><div class="l">Коран</div><div class="v">${c.qu}</div></div></div>
       <div class="s-row"><div class="s-ri">🤲</div><div class="s-rt"><div class="l">Доброе дело</div><div class="v">${c.deed}</div></div></div>`

  const btns = document.getElementById('sl-btns')
  if (locked || done) {
    btns.innerHTML = `<button class="btn btn-o" id="sl-close">Закрыть</button>`
    document.getElementById('sl-close').onclick = () => closeSheetById('lesson')
  } else {
    btns.innerHTML = `
      <button class="btn btn-p" id="sl-review">✍️ Сдать мухасабу</button>
      <button class="btn btn-o" id="sl-close">Закрыть</button>`
    document.getElementById('sl-review').onclick = () => {
      closeSheetById('lesson')
      openSheet('review')
    }
    document.getElementById('sl-close').onclick = () => closeSheetById('lesson')
  }

  openSheet('lesson')
}

function closeSheetById(id) {
  document.getElementById(`ov-${id}`)?.classList.remove('open')
  document.getElementById(`sh-${id}`)?.classList.remove('open')
}
