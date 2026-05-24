import './style.css'
import { initI18n } from './i18n.js'
import { initTg } from './utils/tg.js'
import { initHome, U } from './screens/home.js'
import { setCurrentWeek } from './screens/lessons.js'
import { renderTracker } from './screens/tracker.js'
import { initNav } from './app.js'
import { initDiagnostic, openDiag } from './components/diagnostic.js'
import { initReviewSheet, openReviewSheet } from './components/sheets.js'
import { WEEKS } from './data/weeks.js'

initTg()
initI18n()
initHome()

// Sync currentWeek from user state into lessons module
setCurrentWeek(U.currentWeek)

// Nav
initNav()

// Initial tracker render (for badge dot)
renderTracker()

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
