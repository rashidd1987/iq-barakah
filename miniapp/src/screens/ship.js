import { openLink, cloudGet } from '../utils/tg.js'
import { haptic } from '../utils/tg.js'
import { lang, t } from '../i18n.js'

const SHIP_URL = 'https://rashidd1987.github.io/iq-barakah/ship_barakat_business.html'

export function renderShip() {
  ;['business', 'personal'].forEach(type => {
    const raw = localStorage.getItem('ship_' + type)
    const resultEl = document.getElementById('ship-result-' + type)
    const scoreEl  = document.getElementById('ship-score-' + type)
    const dateEl   = document.getElementById('ship-date-' + type)
    const btnEl    = document.getElementById('ship-btn-' + type)
    if (!raw || !resultEl) return
    try {
      const d = JSON.parse(raw)
      if (!d.scores) return
      const avg = Math.round(d.scores.reduce((s, v) => s + v, 0) / d.scores.length)
      scoreEl.textContent = avg + '%'
      scoreEl.className = 'ship-result-score ' + (avg >= 70 ? 'hi' : avg >= 45 ? 'mid' : 'lo')
      const dt = new Date(d.ts || d.date)
      dateEl.textContent = dt.toLocaleDateString(t('dateLocale'), { day: 'numeric', month: 'short' })
      resultEl.style.display = 'flex'
      btnEl.textContent = (type === 'business' ? '⚓' : '🌙') + ' ' + t('retake')
    } catch (e) {}
  })

  // CloudStorage fallback
  ;['business', 'personal'].forEach(type => {
    if (localStorage.getItem('ship_' + type)) return
    cloudGet('ship_' + type, (err, val) => {
      if (!err && val) {
        localStorage.setItem('ship_' + type, val)
        renderShip()
      }
    })
  })
}

export function openShip(type) {
  haptic()
  openLink(SHIP_URL + '?tab=' + type + '&lang=' + lang())
}

export function initShipButtons() {
  document.getElementById('ship-btn-business')?.addEventListener('click', () => openShip('business'))
  document.getElementById('ship-btn-personal')?.addEventListener('click', () => openShip('personal'))
}
