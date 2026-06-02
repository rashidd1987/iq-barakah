import './style.css'
import { initI18n } from './i18n.js'
import { initTg, cloudGet, cloudSet, haptic, sendData } from './utils/tg.js'
import { initHome, U } from './screens/home.js'
import { setCurrentWeek } from './screens/lessons.js'
import { renderTracker } from './screens/tracker.js'
import { initNav, rerenderCurrentScreen } from './app.js'
import { initDiagnostic, openDiag } from './components/diagnostic.js'
import { initReviewSheet, openReviewSheet } from './components/sheets.js'
import { WEEKS } from './data/weeks.js'
import { lsGet, lsSet } from './utils/storage.js'
import { isChecked, getTrackerPayload } from './screens/tracker.js'
import { NAMAZ, DAILY } from './data/habits.js'
import { PROGRAM_TASKS } from './data/tasks.js'

initTg()
initI18n()
initHome()

// Sync currentWeek from user state into lessons module
setCurrentWeek(U.currentWeek)

// Nav
initNav()

// Sync habits from CloudStorage → merge with localStorage → then render
function _mergeAndRender() {
  cloudGet('iq_checked', (err, value) => {
    if (!err && value) {
      try {
        const cloud = JSON.parse(value)
        const local = lsGet('checked', {})
        // Union merge: if either device checked an item, it stays checked
        const merged = { ...cloud }
        for (const [day, items] of Object.entries(local)) {
          if (!merged[day]) merged[day] = {}
          Object.assign(merged[day], items)
        }
        lsSet('checked', merged)
        cloudSet('iq_checked', JSON.stringify(merged))
      } catch(e) {}
    }
    renderTracker()
  })
}
_mergeAndRender()

// Diagnostic
initDiagnostic(() => {
  // After diag finish — reload home state
  initHome()
  setCurrentWeek(U.currentWeek)
})

// Diagnostic trigger buttons
document.getElementById('btn-open-diag')?.addEventListener('click', openDiag)

// Review sheet (muhasaba)
initReviewSheet(() => U.currentWeek, WEEKS)
document.getElementById('btn-muhasaba')?.addEventListener('click', () =>
  openReviewSheet(U.currentWeek, WEEKS)
)

// Curator report button
document.getElementById('btn-curator-report')?.addEventListener('click', () => {
  haptic()
  const level = U.level
  const LEVEL_OFFSET = { А: 0, Б: 6, В: 14, Г: 22 }
  const weekInLevel = level ? U.currentWeek - (LEVEL_OFFSET[level] ?? 0) : 0

  // Count habits done today
  const allHabits = [...NAMAZ.map(n => n.id), ...DAILY.map(d => d.id)]
  const habitsDone = allHabits.filter(id => isChecked(id)).length

  // Count program tasks done this week
  let tasksDone = 0, tasksTotal = 0
  if (level && weekInLevel > 0 && PROGRAM_TASKS[level]) {
    const weekData = PROGRAM_TASKS[level][weekInLevel - 1]
    if (weekData) {
      const skill = U.skill || 'I'
      const tasks = weekData[skill] || weekData['I'] || []
      tasksTotal = tasks.length
      const storageKey = `ptasks_${level}_w${weekInLevel}_${U.skill}`
      const done = lsGet(storageKey, {})
      tasksDone = Object.values(done).filter(Boolean).length
    }
  }

  sendData({
    action: 'curator_report',
    level,
    week: weekInLevel,
    habitsDone,
    habitsTotal: allHabits.length,
    tasksDone,
    tasksTotal,
    streak: U.streak,
  })
})

window.addEventListener('iq:langchange', () => {
  initHome()
  renderTracker()
  rerenderCurrentScreen()
})
