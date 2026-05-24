import { haptic, sendData } from '../utils/tg.js'
import { showToast } from '../components/sheets.js'
import { t } from '../i18n.js'

const SECTORS = [
  { name: 'Вера (Иман)', color: '#2c5f2d', val: 7 },
  { name: 'Намаз',       color: '#3d7a3e', val: 6 },
  { name: 'Семья',       color: '#c9a84c', val: 8 },
  { name: 'Здоровье',    color: '#5b8fa8', val: 5 },
  { name: 'Ризк',        color: '#7b5ea7', val: 6 },
  { name: 'Знание',      color: '#e07b39', val: 7 },
  { name: 'Ахляк',       color: '#d4547a', val: 8 },
  { name: 'Уммет',       color: '#4a9e8c', val: 5 },
]

export function renderWheel() {
  drawWheel()
  buildSliders()
}

function drawWheel() {
  const cv = document.getElementById('wcanvas')
  if (!cv) return
  const ctx = cv.getContext('2d')
  const cx = 145, cy = 145, r = 122, n = SECTORS.length
  const step = (2 * Math.PI) / n
  ctx.clearRect(0, 0, 290, 290)

  for (let i = 1; i <= 10; i++) {
    ctx.beginPath()
    ctx.arc(cx, cy, (r / 10) * i, 0, 2 * Math.PI)
    ctx.strokeStyle = i === 10 ? '#ccc' : '#eee'
    ctx.lineWidth = i === 10 ? 1.5 : 1
    ctx.stroke()
  }

  SECTORS.forEach((s, i) => {
    const a = -Math.PI / 2 + i * step, ea = a + step, sr = (r / 10) * s.val
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, sr, a, ea); ctx.closePath()
    ctx.fillStyle = s.color + '4a'; ctx.fill()
    ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.stroke()
  })

  SECTORS.forEach((_, i) => {
    const a = -Math.PI / 2 + i * step
    ctx.beginPath(); ctx.moveTo(cx, cy)
    ctx.lineTo(cx + r * Math.cos(a), cy + r * Math.sin(a))
    ctx.strokeStyle = '#ddd'; ctx.lineWidth = 1; ctx.stroke()
  })

  ctx.font = 'bold 11px -apple-system,sans-serif'
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
  SECTORS.forEach((s, i) => {
    const a = -Math.PI / 2 + (i + 0.5) * step, lr = r + 16
    ctx.fillStyle = s.color
    ctx.fillText(s.val, cx + lr * Math.cos(a), cy + lr * Math.sin(a))
  })

  ctx.beginPath(); ctx.arc(cx, cy, 5, 0, 2 * Math.PI)
  ctx.fillStyle = '#2c5f2d'; ctx.fill()
}

function buildSliders() {
  const w = document.getElementById('sliders')
  if (!w) return
  w.innerHTML = ''
  SECTORS.forEach((s, i) => {
    const d = document.createElement('div')
    d.className = 'sl-row'
    d.innerHTML = `
      <div class="sl-label">
        <span class="sn" style="color:${s.color};">● ${s.name}</span>
        <span class="sv" id="sv${i}">${s.val}</span>
      </div>
      <input type="range" min="1" max="10" value="${s.val}" style="accent-color:${s.color};" data-idx="${i}">`
    d.querySelector('input').oninput = e => {
      SECTORS[i].val = parseInt(e.target.value)
      document.getElementById('sv' + i).textContent = e.target.value
      drawWheel()
    }
    w.appendChild(d)
  })
}

export function saveWheel() {
  haptic('success')
  const scores = Object.fromEntries(SECTORS.map(s => [s.name, s.val]))
  sendData({ action: 'save_wheel', scores })
  showToast(t('wheelSaved'))
}
