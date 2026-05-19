import { haptic, sendData } from '../utils/tg.js'

export function openSheet(id) {
  document.getElementById(`ov-${id}`)?.classList.add('open')
  document.getElementById(`sh-${id}`)?.classList.add('open')
}

export function closeSheet(id) {
  document.getElementById(`ov-${id}`)?.classList.remove('open')
  document.getElementById(`sh-${id}`)?.classList.remove('open')
}

export function showToast(msg) {
  let t = document.getElementById('toast')
  if (!t) {
    t = document.createElement('div')
    t.id = 'toast'
    t.style.cssText = 'position:fixed;bottom:90px;left:50%;transform:translateX(-50%) translateY(20px);background:#1a3d1b;color:white;padding:10px 20px;border-radius:20px;font-size:14px;font-weight:600;z-index:200;opacity:0;transition:all .25s ease;white-space:nowrap;max-width:90vw;text-align:center;'
    document.body.appendChild(t)
  }
  t.textContent = msg
  requestAnimationFrame(() => {
    t.style.opacity = '1'; t.style.transform = 'translateX(-50%) translateY(0)'
    setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(-50%) translateY(20px)' }, 2200)
  })
}

// ── Review sheet state ──
let rEmoji = null, rTask = null, rUseful = null

export function initReviewSheet(getCurrentWeek, weeksData) {
  // Emoji buttons
  document.querySelectorAll('.em-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      haptic()
      document.querySelectorAll('.em-btn').forEach(b => b.classList.remove('sel'))
      btn.classList.add('sel')
      rEmoji = btn.dataset.emoji
    })
  })

  // Rating rows
  ;['rt-task', 'rt-useful'].forEach(id => {
    const row = document.getElementById(id)
    if (!row) return
    ;[1, 2, 3, 4, 5].forEach(n => {
      const b = document.createElement('button')
      b.className = 'rb'; b.textContent = n
      b.addEventListener('click', () => {
        haptic()
        row.querySelectorAll('.rb').forEach(x => x.classList.remove('sel'))
        b.classList.add('sel')
        if (id === 'rt-task') rTask = n; else rUseful = n
      })
      row.appendChild(b)
    })
  })

  // Submit
  document.getElementById('rv-btn')?.addEventListener('click', () => {
    const text = document.getElementById('rv-text')?.value?.trim()
    if (!rEmoji || !rTask || !text) {
      haptic('error')
      showToast('Выберите настроение, оценку и напишите отзыв')
      return
    }
    const btn = document.getElementById('rv-btn')
    btn.innerHTML = '<div class="spin"></div> Отправляем...'
    btn.disabled = true
    setTimeout(() => {
      haptic('success')
      document.getElementById('rv-form').style.display = 'none'
      document.getElementById('rv-ok').classList.add('show')
      sendData({ type: 'review', week: getCurrentWeek(), emoji: rEmoji, task: rTask, useful: rUseful, text })
    }, 1100)
  })

  // OK button
  document.getElementById('rv-ok-btn')?.addEventListener('click', () => {
    closeSheet('review')
    import('../app.js').then(m => m.switchScreen('lessons'))
  })

  // Overlay click to close
  document.getElementById('ov-lesson')?.addEventListener('click', () => closeSheet('lesson'))
  document.getElementById('ov-review')?.addEventListener('click', () => closeSheet('review'))
}

export function openReviewSheet(currentWeek, weeksData) {
  haptic()
  const lbl = document.getElementById('rv-week-lbl')
  if (lbl && currentWeek > 0 && currentWeek <= weeksData.length) {
    const cw = weeksData[currentWeek - 1]
    if (cw) lbl.textContent = `${cw.num} · ${cw.title} · Три вопроса`
  }
  openSheet('review')
}
