import './style.css'
import { initI18n } from './i18n.js'
import { initTg, cloudGet, cloudSet } from './utils/tg.js'
import { initHome, U } from './screens/home.js'
import { setCurrentWeek } from './screens/lessons.js'
import { renderTracker } from './screens/tracker.js'
import { initNav, rerenderCurrentScreen } from './app.js'
import { initDiagnostic, openDiag } from './components/diagnostic.js'
import { initReviewSheet, openReviewSheet } from './components/sheets.js'
import { WEEKS } from './data/weeks.js'
import { lsGet, lsSet } from './utils/storage.js'

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

window.addEventListener('iq:langchange', () => {
  initHome()
  renderTracker()
  rerenderCurrentScreen()
})
