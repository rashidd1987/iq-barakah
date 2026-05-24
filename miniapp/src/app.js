import { haptic } from './utils/tg.js'
import { renderTracker } from './screens/tracker.js'
import { renderLessons } from './screens/lessons.js'
import { renderWheel, saveWheel } from './screens/wheel.js'
import { renderShip, initShipButtons } from './screens/ship.js'

const SCREENS = ['home', 'tracker', 'lessons', 'wheel', 'ship']
let current = 'home'

export function switchScreen(id) {
  if (!SCREENS.includes(id)) return
  haptic()
  document.getElementById(`sc-${current}`)?.classList.remove('active')
  document.getElementById(`nb-${current}`)?.classList.remove('active')
  document.getElementById(`sc-${id}`)?.classList.add('active')
  document.getElementById(`nb-${id}`)?.classList.add('active')
  current = id

  if (id === 'wheel')   renderWheel()
  if (id === 'lessons') renderLessons('all')
  if (id === 'tracker') renderTracker()
  if (id === 'ship')    renderShip()
}

export function rerenderCurrentScreen() {
  if (current === 'wheel')   renderWheel()
  if (current === 'lessons') renderLessons('all')
  if (current === 'tracker') renderTracker()
  if (current === 'ship')    renderShip()
}

export function initNav() {
  // Nav buttons
  document.querySelectorAll('.nb[data-screen]').forEach(btn => {
    btn.addEventListener('click', () => switchScreen(btn.dataset.screen))
  })

  // Act items on home
  document.querySelectorAll('.act-item[data-screen]').forEach(el => {
    el.addEventListener('click', () => switchScreen(el.dataset.screen))
  })

  // Week banner → lessons
  document.getElementById('cw-banner')?.addEventListener('click', () => switchScreen('lessons'))

  // Wheel save
  document.getElementById('btn-save-wheel')?.addEventListener('click', saveWheel)

  // Ship buttons
  initShipButtons()

  // Phase filter chips
  document.querySelectorAll('.chip[data-phase]').forEach(chip => {
    chip.addEventListener('click', () => {
      haptic()
      document.querySelectorAll('.chip').forEach(c => { c.classList.remove('on'); c.classList.add('off') })
      chip.classList.add('on'); chip.classList.remove('off')
      renderLessons(chip.dataset.phase)
    })
  })
}
