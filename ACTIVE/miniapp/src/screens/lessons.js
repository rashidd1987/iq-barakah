import { WEEKS, PHASE_LABELS } from '../data/weeks.js'
import { TASKS } from '../data/tasks.js'
import { haptic, sendData, cloudGet, cloudSet } from '../utils/tg.js'
import { openSheet } from '../components/sheets.js'
import { t } from '../i18n.js'
import { U } from './home.js'
import { lsGet, lsSet } from '../utils/storage.js'

export let currentWeek = 0

export function setCurrentWeek(w) { currentWeek = w }

// ── Storage helpers ──────────────────────────────────────────────────────────
function taskKey(level, week) { return `tasks_${level}_${week}` }

function loadChecked(level, week) {
  // Try localStorage first (fast, synchronous)
  return lsGet(taskKey(level, week), {})
}

function saveChecked(level, week, state) {
  lsSet(taskKey(level, week), state)
  // Also sync to Telegram CloudStorage for cross-device persistence
  cloudSet(taskKey(level, week), JSON.stringify(state))
}

// ── Get tasks for current user ────────────────────────────────────────────────
function getWeekTasks(level, weekInLevel) {
  const prog = TASKS[level]
  if (!prog) return []
  const weekData = prog[weekInLevel - 1]
  if (!weekData) return []
  const skill = U.skill || 'I'
  return weekData[skill] || weekData['I'] || []
}

// ── Render lessons list ───────────────────────────────────────────────────────
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

    // Task completion progress for this week
    const level = U.level
    let taskPct = 0
    if (!locked && level) {
      // Figure out week index within the program level
      const { levelWeekIndex } = weekToLevelIndex(wi)
      if (levelWeekIndex > 0) {
        const tasks = getWeekTasks(level, levelWeekIndex)
        if (tasks.length > 0) {
          const checked = loadChecked(level, levelWeekIndex)
          const doneCount = Object.values(checked).filter(Boolean).length
          taskPct = Math.round(doneCount / tasks.length * 100)
        }
      }
    }

    const progressBadge = (!locked && taskPct > 0)
      ? `<div class="task-pct">${taskPct}%</div>`
      : ''

    const el = document.createElement('div')
    el.className = `week-item${isCur ? ' week-item-current' : ''}`
    el.innerHTML = `
      <div class="wnum ${locked ? 'lock' : done ? 'done' : 'cur'}">${w.num}</div>
      <div class="winfo">
        <div class="t">${w.icon} ${w.title}</div>
        <div class="s">${w.sub}</div>
      </div>
      <div class="wstat">${locked ? '🔒' : done ? '✅' : progressBadge || '📖'}</div>`
    el.onclick = () => openLessonSheet(w, done, isCur, locked, wi)
    list.appendChild(el)
    if (isCur) curEl = el
  })

  if (curEl) setTimeout(() => curEl.scrollIntoView({ behavior: 'smooth', block: 'center' }), 120)

  // Sync progress bar
  const pct = currentWeek > 0 ? Math.round(Math.max(0, currentWeek - 1) / 30 * 100) : 0
  const bar = document.getElementById('lessons-pbar')
  if (bar) bar.style.width = pct + '%'
}

// ── Convert global week index → level + local week ────────────────────────────
function weekToLevelIndex(globalWeekIndex) {
  // LEVEL_OFFSET is in weeks.js: {А: 0, Б: 6, В: 14, Г: 22}
  // But we work with 1-based globalWeekIndex
  const level = U.level
  if (!level) return { levelWeekIndex: 0 }

  const offsets = { А: 0, Б: 6, В: 14, Г: 22 }
  const offset = offsets[level] ?? 0
  const levelWeekIndex = globalWeekIndex - offset
  return { levelWeekIndex }
}

// ── Open lesson detail sheet ──────────────────────────────────────────────────
function openLessonSheet(w, done, isCur, locked, globalWeekIndex) {
  haptic()
  document.getElementById('sl-icon').textContent  = w.icon
  document.getElementById('sl-title').textContent = w.title
  document.getElementById('sl-sub').textContent   = `${w.sub} · ${locked ? t('locked') : done ? t('completedLesson') : t('current')}`

  const rows = document.getElementById('sl-rows')
  if (locked) {
    rows.innerHTML = `
      <div class="s-row">
        <div class="s-ri">🔒</div>
        <div class="s-rt">
          <div class="l">${t('howToOpen')}</div>
          <div class="v">${t('unlockHint')}</div>
        </div>
      </div>`
  } else {
    const level = U.level
    const { levelWeekIndex } = weekToLevelIndex(globalWeekIndex)
    const tasks = getWeekTasks(level, levelWeekIndex)
    const checked = loadChecked(level, levelWeekIndex)

    rows.innerHTML = _renderTasksHtml(tasks, checked, level, levelWeekIndex)
    _bindCheckboxes(rows, level, levelWeekIndex, tasks)
  }

  const btns = document.getElementById('sl-btns')
  if (locked || done) {
    btns.innerHTML = `<button class="btn btn-o" id="sl-close">${t('close')}</button>`
    document.getElementById('sl-close').onclick = () => closeSheetById('lesson')
  } else {
    btns.innerHTML = `
      <button class="btn btn-p" id="sl-review">${t('submitMuhasaba')}</button>
      <button class="btn btn-o" id="sl-close">${t('close')}</button>`
    document.getElementById('sl-review').onclick = () => {
      closeSheetById('lesson')
      openSheet('review')
    }
    document.getElementById('sl-close').onclick = () => closeSheetById('lesson')
  }

  openSheet('lesson')
}

// ── Tasks HTML ────────────────────────────────────────────────────────────────
function _renderTasksHtml(tasks, checked, level, weekInLevel) {
  if (!tasks || tasks.length === 0) {
    return `<div class="s-row"><div class="s-ri">📋</div><div class="s-rt"><div class="l">Задания</div><div class="v">Задания появятся скоро</div></div></div>`
  }

  const doneCount = Object.values(checked).filter(Boolean).length
  const total = tasks.length
  const pct = total > 0 ? Math.round(doneCount / total * 100) : 0

  let html = `
    <div class="tasks-header">
      <div class="tasks-title">📋 Задания недели</div>
      <div class="tasks-progress">
        <div class="tasks-pbar-wrap">
          <div class="tasks-pbar" style="width:${pct}%"></div>
        </div>
        <div class="tasks-pct">${doneCount}/${total}</div>
      </div>
    </div>`

  tasks.forEach((task, i) => {
    const isChecked = !!checked[i]
    html += `
      <label class="task-item${isChecked ? ' task-done' : ''}" data-task-idx="${i}">
        <span class="task-cb${isChecked ? ' checked' : ''}">
          ${isChecked ? '✅' : '⬜'}
        </span>
        <span class="task-text">${task}</span>
      </label>`
  })

  return html
}

// ── Bind checkbox interactions ────────────────────────────────────────────────
function _bindCheckboxes(container, level, weekInLevel, tasks) {
  container.querySelectorAll('.task-item').forEach(item => {
    item.addEventListener('click', () => {
      haptic()
      const idx = parseInt(item.dataset.taskIdx, 10)
      const checked = loadChecked(level, weekInLevel)
      const newVal = !checked[idx]
      checked[idx] = newVal

      saveChecked(level, weekInLevel, checked)

      // Update UI inline (no re-render, smooth UX)
      const cb = item.querySelector('.task-cb')
      if (newVal) {
        cb.textContent = '✅'
        cb.classList.add('checked')
        item.classList.add('task-done')
      } else {
        cb.textContent = '⬜'
        cb.classList.remove('checked')
        item.classList.remove('task-done')
      }

      // Update progress bar
      const doneCount = Object.values(checked).filter(Boolean).length
      const total = tasks.length
      const pct = Math.round(doneCount / total * 100)
      const pbar = container.querySelector('.tasks-pbar')
      const pctEl = container.querySelector('.tasks-pct')
      if (pbar) pbar.style.width = pct + '%'
      if (pctEl) pctEl.textContent = `${doneCount}/${total}`

      // Send to bot (saves to PostgreSQL, notifies curator if all done)
      sendData({
        action: 'check_task',
        level,
        week: weekInLevel,
        task_index: idx,
        checked: newVal,
        total_tasks: total,
      })

      // Celebration if all done
      if (doneCount === total) {
        haptic('success')
        setTimeout(() => _showAllDoneBanner(container), 200)
      }
    })
  })
}

// ── All done celebration ──────────────────────────────────────────────────────
function _showAllDoneBanner(container) {
  const existing = container.querySelector('.all-done-banner')
  if (existing) return
  const banner = document.createElement('div')
  banner.className = 'all-done-banner'
  banner.innerHTML = `
    <div class="all-done-icon">🎉</div>
    <div class="all-done-text">Все задания выполнены! Альхамдулиллях</div>`
  container.appendChild(banner)
}

function closeSheetById(id) {
  document.getElementById(`ov-${id}`)?.classList.remove('open')
  document.getElementById(`sh-${id}`)?.classList.remove('open')
}
