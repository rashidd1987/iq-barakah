// Onboarding flow — shown once after first registration
// Steps: welcome → tracker intro → lessons intro → notifications ask

const STEPS = [
  {
    icon: '🌱',
    title: 'Добро пожаловать в IQ Barakah',
    text: 'Система роста мусульманина — привычки, знания и духовное развитие в одном месте.',
    cta: 'Начать →',
  },
  {
    icon: '📅',
    title: 'Трекер привычек',
    text: 'Каждый день отмечай намазы и добрые дела. Стрик мотивирует не пропускать.',
    cta: 'Понятно →',
    highlight: 'tracker',
  },
  {
    icon: '📚',
    title: 'Программа обучения',
    text: '30 недель структурированного роста. Уроки, задания и тесты по твоему уровню.',
    cta: 'Отлично →',
    highlight: 'lessons',
  },
  {
    icon: '🔔',
    title: 'Разреши уведомления',
    text: 'Напомним о намазе и ежедневном задании. Без уведомлений легко забыть.',
    cta: 'Разрешить',
    ctaSecondary: 'Пропустить',
    action: 'push',
  },
]

let step = 0
let overlay, card, dotWrap

export function initOnboarding(onDone) {
  if (localStorage.getItem('iq_onboarded')) { onDone(); return }

  overlay = document.createElement('div')
  overlay.id = 'onboard-overlay'
  overlay.innerHTML = `
    <div id="onboard-card">
      <div id="ob-icon"></div>
      <h2 id="ob-title"></h2>
      <p id="ob-text"></p>
      <div id="ob-dots"></div>
      <button class="btn btn-p" id="ob-cta"></button>
      <button class="btn btn-o" id="ob-skip" style="display:none"></button>
    </div>
  `
  document.body.appendChild(overlay)

  card = document.getElementById('onboard-card')
  dotWrap = document.getElementById('ob-dots')

  document.getElementById('ob-cta').addEventListener('click', () => _handleCta(onDone))
  document.getElementById('ob-skip').addEventListener('click', () => _next(onDone))

  _render()
}

function _render() {
  const s = STEPS[step]
  const icon = document.getElementById('ob-icon')
  const title = document.getElementById('ob-title')
  const text = document.getElementById('ob-text')
  const cta = document.getElementById('ob-cta')
  const skip = document.getElementById('ob-skip')

  // animate out
  card.classList.remove('ob-in')
  card.classList.add('ob-out')

  setTimeout(() => {
    icon.textContent = s.icon
    title.textContent = s.title
    text.textContent = s.text
    cta.textContent = s.cta
    skip.style.display = s.ctaSecondary ? 'flex' : 'none'
    if (s.ctaSecondary) skip.textContent = s.ctaSecondary

    // dots
    dotWrap.innerHTML = STEPS.map((_, i) =>
      `<div class="ob-dot ${i === step ? 'active' : ''}"></div>`
    ).join('')

    card.classList.remove('ob-out')
    card.classList.add('ob-in')
  }, 180)
}

async function _handleCta(onDone) {
  const s = STEPS[step]
  if (s.action === 'push') {
    try {
      const perm = await Notification.requestPermission()
      if (perm === 'granted') _scheduleDailyReminder()
    } catch {}
  }
  _next(onDone)
}

function _next(onDone) {
  step++
  if (step >= STEPS.length) {
    localStorage.setItem('iq_onboarded', '1')
    overlay.classList.add('ob-fade-out')
    setTimeout(() => { overlay.remove(); onDone() }, 350)
  } else {
    _render()
  }
}

function _scheduleDailyReminder() {
  if (!('serviceWorker' in navigator)) return
  navigator.serviceWorker.ready.then(reg => {
    // Store pref — actual push needs backend subscription
    localStorage.setItem('iq_push_granted', '1')
  })
}
