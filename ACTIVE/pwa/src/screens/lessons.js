import { WEEKS, PHASE_LABELS } from '../data/weeks.js'
import { PROGRAM_TASKS } from '../data/tasks.js'
import { PROGRAM_CONTENT } from '../data/content.js'
import { LESSON_SUMMARIES } from '../data/vakt_summaries.js'
import { getStepTest } from '../data/step_tests.js'
import { haptic, sendData, cloudGet, cloudSet, openLink } from '../utils/tg.js'
import { openSheet, closeSheet } from '../components/sheets.js'
import { t } from '../i18n.js'
import { U } from './home.js'
import { lsGet, lsSet } from '../utils/storage.js'

export let currentWeek = 0

// ── Step test ─────────────────────────────────────────────────────────────────
let _stCur = 0, _stAns = [], _stQs = [], _stScore = 0

export function openStepTest(globalWeekIndex, weekTitle) {
  const { level, levelWeekIndex } = weekToLevelIndex(globalWeekIndex)
  _stQs = getStepTest(level, levelWeekIndex, U.skill || 'I')

  if (_stQs.length === 0) {
    // No test for this step — unlock immediately
    _unlockNextStep(globalWeekIndex)
    return
  }

  _stCur = 0
  _stScore = 0
  _stAns = new Array(_stQs.length).fill(null)

  const icon = WEEKS[globalWeekIndex - 1]?.icon || '📝'
  document.getElementById('st-icon').textContent = icon
  document.getElementById('st-title').textContent = 'Тест шага: ' + weekTitle
  document.getElementById('st-sub').textContent = _stQs.length + ' вопросов · 2 из 3 правильно = шаг открыт'

  document.getElementById('st-quiz').style.display = ''
  document.getElementById('st-result').style.display = 'none'

  _renderStepQ(globalWeekIndex)
  openSheet('steptest')

  document.getElementById('ov-steptest')?.addEventListener('click', e => {
    if (e.target === e.currentTarget) closeSheet('steptest')
  }, { once: true })
}

function _renderStepQ(globalWeekIndex) {
  const q = _stQs[_stCur]
  const pct = Math.round((_stCur + 1) / _stQs.length * 100)
  document.getElementById('st-prog-fill').style.width = pct + '%'
  document.getElementById('st-frac').textContent = (_stCur + 1) + ' / ' + _stQs.length
  document.getElementById('st-qtext').textContent = q.q

  const og = document.getElementById('st-opts')
  og.innerHTML = q.opts.map((o, i) => `
    <button class="st-opt" data-i="${i}">
      <span class="st-opt-num">${String.fromCharCode(65 + i)}</span>
      <span>${o}</span>
    </button>`).join('')

  og.querySelectorAll('.st-opt').forEach(btn => {
    btn.addEventListener('click', () => {
      
      const chosen = parseInt(btn.dataset.i)
      const correct = q.correct
      const isCorrect = chosen === correct

      // Show correct/wrong feedback
      og.querySelectorAll('.st-opt').forEach(b => {
        const bi = parseInt(b.dataset.i)
        if (bi === correct) b.classList.add('st-correct')
        else if (bi === chosen && !isCorrect) b.classList.add('st-wrong')
        b.disabled = true
      })

      if (isCorrect) _stScore++

      setTimeout(() => {
        if (_stCur < _stQs.length - 1) {
          _stCur++
          _renderStepQ(globalWeekIndex)
        } else {
          _showStepResult(globalWeekIndex)
        }
      }, 700)
    })
  })
}

function _showStepResult(globalWeekIndex) {
  document.getElementById('st-quiz').style.display = 'none'
  const passed = _stScore >= Math.ceil(_stQs.length * 2 / 3)
  const resEl = document.getElementById('st-result')
  resEl.style.display = ''

  document.getElementById('st-res-title').textContent = passed
    ? `✅ Отлично! ${_stScore} из ${_stQs.length} верно`
    : `📚 ${_stScore} из ${_stQs.length} верно`
  document.getElementById('st-res-sub').textContent = passed
    ? 'Шаг завершён — следующий открыт!'
    : 'Повтори урок и попробуй снова'

  const nextBtn = document.getElementById('st-next-btn')
  const closeBtn = document.getElementById('st-close-btn')

  nextBtn.style.display = passed ? '' : 'none'
  closeBtn.textContent = passed ? 'Закрыть' : '← Назад к уроку'

  nextBtn.onclick = () => { closeSheet('steptest'); _unlockNextStep(globalWeekIndex) }
  closeBtn.onclick = () => closeSheet('steptest')
}

function _unlockNextStep(globalWeekIndex) {
  if (globalWeekIndex >= currentWeek) {
    currentWeek = globalWeekIndex + 1
    U.currentWeek = currentWeek
    lsSet('currentWeek', currentWeek)
    cloudSet('currentWeek', String(currentWeek))
  }
  renderLessons()
  const pct = Math.round(Math.max(0, currentWeek - 1) / 30 * 100)
  document.getElementById('rpct').textContent = pct + '%'
  const circ = 2 * Math.PI * 62
  document.getElementById('ring')?.setAttribute('stroke-dashoffset', (circ * (1 - pct / 100)).toFixed(1))
  document.getElementById('sv-weeks').textContent = Math.max(0, currentWeek - 1)
}

export function setCurrentWeek(w) { currentWeek = w }

// ── Storage helpers ──────────────────────────────────────────────────────────
function taskKey(level, week) {
  const today = new Date().toISOString().split('T')[0]
  return `ptasks_${level}_w${week}_${(typeof U !== 'undefined' ? U.skill : 'I') || 'I'}_${today}`
}

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
    if (!locked) {
      const { level: wLevel, levelWeekIndex } = weekToLevelIndex(wi)
      if (levelWeekIndex > 0) {
        const tasks = getWeekTasks(wLevel, levelWeekIndex)
        if (tasks.length > 0) {
          const checked = loadChecked(wLevel, levelWeekIndex)
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
  // Determine level from the global week number (not from U.level)
  // ВАКТ: 1-6 → А, Сезон1: 7-14 → Б, Сезон2: 15-22 → В, Сезон3: 23-30 → Г
  let level, offset
  if (globalWeekIndex <= 6)       { level = 'А'; offset = 0 }
  else if (globalWeekIndex <= 14) { level = 'Б'; offset = 6 }
  else if (globalWeekIndex <= 22) { level = 'В'; offset = 14 }
  else                            { level = 'Г'; offset = 22 }

  const levelWeekIndex = globalWeekIndex - offset
  return { level, levelWeekIndex }
}

// ── Open lesson detail sheet ──────────────────────────────────────────────────
function openLessonSheet(w, done, isCur, locked, globalWeekIndex) {
  
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
    const { level, levelWeekIndex } = weekToLevelIndex(globalWeekIndex)
    const skill = U.skill || 'I'
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
      <button class="btn btn-cal" id="sl-calendar">📅 Добавить в календарь</button>
      <button class="btn btn-o" id="sl-close">${t('close')}</button>`
    document.getElementById('sl-fullbot').onclick = () => {
      sendData({ action: 'open_lesson', level: U.level, week: weekToLevelIndex(globalWeekIndex).levelWeekIndex })
    }
    document.getElementById('sl-calendar')?.addEventListener('click', () => {
      
      _openCalendar(w, globalWeekIndex)
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
  const summary = LESSON_SUMMARIES?.[level]?.[weekInLevel - 1]?.[skill] || null

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

  let html = `<div class="lesson-tasks-list"><div class="lesson-tasks-title">📋 Задания шага</div>`
  tasks.forEach((task, i) => {
    html += `<div class="lesson-task-row"><span class="lesson-task-num">${i + 1}</span><span class="lesson-task-text">${task}</span></div>`
  })
  html += `<div class="lesson-tasks-hint">🔁 Выполняй каждый день · ✅ Отмечай в Трекере</div></div>`
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

function _openCalendar(w, globalWeekIndex) {
  const { levelWeekIndex } = weekToLevelIndex(globalWeekIndex)
  const tasks = getWeekTasks(U.level, levelWeekIndex)

  // Monday of the current week
  const today = new Date()
  const dow = today.getDay()
  const monday = new Date(today)
  monday.setDate(today.getDate() - ((dow + 6) % 7))

  const pad = n => String(n).padStart(2, '0')
  const fmt = d => `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}T${pad(d.getHours())}${pad(d.getMinutes())}00`

  // Clean task text for ICS
  const taskDesc = tasks.map((t, i) =>
    `${i+1}. ${t.replace(/[^ -~Ѐ-ӿ\s.,!?—·🕐📿📖🌙⏰🌤]/g, '').substring(0, 120).trim()}`
  ).join('\\n')

  const summary = `IQ Barakah · ${w.num} · ${w.title}`
  const desc = `${w.sub}\\n\\nЗадания на каждый день шага:\\n${taskDesc}\\n\\nОтмечай выполненное в Трекере ✅`

  // Generate 7 separate VEVENT entries (Mon–Sun, 9:00–9:30)
  const CRLF = '\r\n'
  let vevents = ''
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    d.setHours(9, 0, 0, 0)
    const dEnd = new Date(d)
    dEnd.setHours(9, 30, 0, 0)
    const uid = `iqb-${w.num}-day${i+1}-${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}@iq-barakah`
    vevents += `BEGIN:VEVENT${CRLF}UID:${uid}${CRLF}DTSTART:${fmt(d)}${CRLF}DTEND:${fmt(dEnd)}${CRLF}SUMMARY:${summary}${CRLF}DESCRIPTION:${desc}${CRLF}END:VEVENT${CRLF}`
  }

  const ics = `BEGIN:VCALENDAR${CRLF}VERSION:2.0${CRLF}PRODID:-//IQ Barakah//RU${CRLF}${vevents}END:VCALENDAR`

  // data: URI — works on iOS/Apple Calendar, Android, Google Calendar, Outlook
  const encoded = encodeURIComponent(ics)
  window.open(`data:text/calendar;charset=utf-8,${encoded}`)
}

function closeSheetById(id) {
  document.getElementById(`ov-${id}`)?.classList.remove('open')
  document.getElementById(`sh-${id}`)?.classList.remove('open')
}
