import { renderTracker } from './screens/tracker.js'
import { renderLessons } from './screens/lessons.js'
import { renderWheel, saveWheel } from './screens/wheel.js'
import { renderShip, initShipButtons } from './screens/ship.js'
import { trackScreen } from './analytics.js'

const SCREENS = ['home', 'tracker', 'lessons', 'wheel', 'ship']
const SCREEN_ORDER = { home: 0, tracker: 1, lessons: 2, wheel: 3, ship: 4 }
let current = 'home'

export function switchScreen(id) {
  if (!SCREENS.includes(id) || id === current) return
  const prevEl = document.getElementById(`sc-${current}`)
  const nextEl = document.getElementById(`sc-${id}`)
  if (!prevEl || !nextEl) return

  const goRight = SCREEN_ORDER[id] > SCREEN_ORDER[current]

  // slide out current
  prevEl.classList.add(goRight ? 'slide-out-left' : 'slide-out-right')
  prevEl.classList.remove('active')

  // prepare next
  nextEl.classList.add(goRight ? 'slide-in-right' : 'slide-in-left')
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      nextEl.classList.add('active')
      nextEl.classList.remove('slide-in-right', 'slide-in-left')
    })
  })
  setTimeout(() => {
    prevEl.classList.remove('slide-out-left', 'slide-out-right')
  }, 320)

  const prevBtn = document.getElementById(`nb-${current}`)
  const nextBtn = document.getElementById(`nb-${id}`)
  prevBtn?.classList.remove('active')
  prevBtn?.removeAttribute('aria-current')
  nextBtn?.classList.add('active')
  nextBtn?.setAttribute('aria-current', 'page')
  current = id

  trackScreen(id)
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

export function initApp() {
  document.querySelectorAll('.nb[data-screen]').forEach(btn => {
    btn.addEventListener('click', () => switchScreen(btn.dataset.screen))
  })
  document.querySelectorAll('.act-item[data-screen]').forEach(el => {
    el.addEventListener('click', () => switchScreen(el.dataset.screen))
  })
  document.getElementById('cw-banner')?.addEventListener('click', () => switchScreen('lessons'))
  document.getElementById('btn-save-wheel')?.addEventListener('click', saveWheel)
  initShipButtons()
  document.querySelectorAll('.chip[data-phase]').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.chip').forEach(c => { c.classList.remove('on'); c.classList.add('off') })
      chip.classList.add('on'); chip.classList.remove('off')
      renderLessons(chip.dataset.phase)
    })
  })
}

// Sheet helpers (global)
window.openSheet = function(html) {
  document.getElementById('sheet-content').innerHTML = html
  document.getElementById('overlay').classList.add('open')
  document.getElementById('sheet').classList.add('open')
}
window.closeSheet = function() {
  document.getElementById('overlay').classList.remove('open')
  document.getElementById('sheet').classList.remove('open')
}
window.closeGlossary = function() {
  document.getElementById('glossary-popup').classList.remove('show')
}
