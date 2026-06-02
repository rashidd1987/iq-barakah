import { WEEKS, PHASE_LABELS } from '../data/weeks.js'
import { PROGRAM_TASKS } from '../data/tasks.js'
import { PROGRAM_CONTENT } from '../data/content.js'
import { haptic, sendData, cloudGet, cloudSet } from '../utils/tg.js'
import { openSheet } from '../components/sheets.js'
import { t } from '../i18n.js'
import { U } from './home.js'
import { lsGet } from '../utils/storage.js'

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
  const prog = PROGRAM_TASKS[level]
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
    const content = _getLessonContent(level, levelWeekIndex)

    rows.innerHTML = _renderLessonContent(content, level, levelWeekIndex) + _renderTasksHtml(tasks)
  }

  const btns = document.getElementById('sl-btns')
  if (locked) {
    btns.innerHTML = `<button class="btn btn-o" id="sl-close">${t('close')}</button>`
    document.getElementById('sl-close').onclick = () => closeSheetById('lesson')
  } else {
    btns.innerHTML = `
      <button class="btn btn-p" id="sl-fullbot">📖 Полный урок в боте</button>
      ${!done ? `<button class="btn btn-p2" id="sl-review">${t('submitMuhasaba')}</button>` : ''}
      <button class="btn btn-o" id="sl-close">${t('close')}</button>`
    document.getElementById('sl-fullbot').onclick = () => {
      sendData({ action: 'open_lesson', level: U.level, week: weekToLevelIndex(globalWeekIndex).levelWeekIndex })
    }
    document.getElementById('sl-review')?.addEventListener('click', () => {
      closeSheetById('lesson')
      openSheet('review')
    })
    document.getElementById('sl-close').onclick = () => closeSheetById('lesson')
  }

  openSheet('lesson')
}

// ── Lesson content from PROGRAM_CONTENT ───────────────────────────────────────
function _getLessonContent(level, weekInLevel) {
  if (!level || !weekInLevel) return null
  const levelData = PROGRAM_CONTENT[level]
  if (!levelData) return null
  return levelData[weekInLevel - 1] || null
}

function _renderLessonContent(content, level, weekInLevel) {
  if (!content) return ''
  const skill = U.skill || 'I'

  // Use curated summary if available
  const summary = (typeof LESSON_SUMMARIES !== 'undefined')
    ? LESSON_SUMMARIES?.[level]?.[weekInLevel - 1]?.[skill]
    : null

  let html = ''
  if (content.hadith) {
    html += `<div class="lesson-hadith">
      <div class="hadith-icon">📜</div>
      <div class="hadith-text">${content.hadith}</div>
    </div>`
  }

  if (summary) {
    html += `<div class="lesson-text-preview"><p>${summary}</p><div class="lesson-read-more">📖 Полный текст — в боте</div></div>`
  } else {
    // Fallback: first 2 paragraphs
    const text = typeof content.text === 'object' ? (content.text[skill] || content.text['I'] || '') : (content.text || '')
    const paragraphs = text.split(/\n\n+/).map(p => p.trim()).filter(Boolean)
    const preview = paragraphs.slice(0, 2)
    if (preview.length > 0) {
      const previewHtml = preview.map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('')
      html += `<div class="lesson-text-preview">${previewHtml}<div class="lesson-read-more">📖 Полный текст — в боте</div></div>`
    }
  }
  return html
}

// ── Tasks HTML ────────────────────────────────────────────────────────────────
function _renderTasksHtml(tasks) {
  if (!tasks || tasks.length === 0) return ''

  let html = `<div class="lesson-tasks-list"><div class="lesson-tasks-title">📋 Задания недели</div>`
  tasks.forEach((task, i) => {
    html += `<div class="lesson-task-row"><span class="lesson-task-num">${i + 1}</span><span class="lesson-task-text">${task}</span></div>`
  })
  html += `<div class="lesson-tasks-hint">✅ Отмечай выполненное в Трекере</div></div>`
  return html
}

// ── All done celebration ──────────────────────────────────────────────────────
function _showAllDoneBanner(container) {
  const existing = container.querySelector('.all-done-banner')
  if (existing) return
  const banner = document.createElement('div')
  banner.className = 'all-done-banner'
  banner.innerHTML = `
    <div class="all-done-icon">🎉</div>
    <div>
      <div class="all-done-text">Все задания выполнены! Альхамдулиллях</div>
      <div class="all-done-sub">Ты молодец — продолжай в том же духе 💚</div>
    </div>`
  container.appendChild(banner)
}

function closeSheetById(id) {
  document.getElementById(`ov-${id}`)?.classList.remove('open')
  document.getElementById(`sh-${id}`)?.classList.remove('open')
}
