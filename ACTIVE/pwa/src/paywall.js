// In-app paywall — shown when user tries to access premium content without subscription
// Redirects to YooKassa payment or Telegram bot for payment

const PLANS = [
  {
    id: 'month',
    name: '1 месяц',
    price: '990 ₽',
    priceNum: 990,
    period: '/мес',
    badge: null,
  },
  {
    id: 'quarter',
    name: '3 месяца',
    price: '2 490 ₽',
    priceNum: 2490,
    period: '/3 мес',
    badge: 'Популярный',
    saving: 'Экономия 480 ₽',
  },
  {
    id: 'year',
    name: '12 месяцев',
    price: '7 990 ₽',
    priceNum: 7990,
    period: '/год',
    badge: 'Лучший выбор',
    saving: 'Экономия 3 890 ₽',
  },
]

let _selectedPlan = 'quarter'

export function isPremium() {
  const exp = localStorage.getItem('iq_premium_exp')
  if (!exp) return false
  return Date.now() < parseInt(exp, 10)
}

export function openPaywall(reason = '') {
  if (document.getElementById('paywall-overlay')) return

  const overlay = document.createElement('div')
  overlay.id = 'paywall-overlay'
  overlay.innerHTML = `
    <div class="pw-sheet">
      <button class="pw-close" onclick="document.getElementById('paywall-overlay').remove()">✕</button>
      <div class="pw-crown">👑</div>
      <h2 class="pw-title">IQ Barakah Premium</h2>
      <p class="pw-reason">${reason || 'Полный доступ к программе 30 недель'}</p>
      <ul class="pw-perks">
        <li>✅ Все 30 недель программы</li>
        <li>✅ Персональный анализ Корабля</li>
        <li>✅ Колесо жизни мусульманина</li>
        <li>✅ Трекер привычек с аналитикой</li>
        <li>✅ Поддержка куратора</li>
      </ul>
      <div class="pw-plans">
        ${PLANS.map(p => `
          <div class="pw-plan ${p.id === _selectedPlan ? 'selected' : ''}" data-plan="${p.id}" onclick="_pwSelectPlan('${p.id}')">
            ${p.badge ? `<div class="pw-badge">${p.badge}</div>` : ''}
            <div class="pw-plan-name">${p.name}</div>
            <div class="pw-plan-price">${p.price}<span>${p.period}</span></div>
            ${p.saving ? `<div class="pw-saving">${p.saving}</div>` : ''}
          </div>
        `).join('')}
      </div>
      <button class="btn btn-p pw-buy" id="pw-buy-btn" onclick="_pwBuy()">Оформить подписку</button>
      <p class="pw-trial">Пробный период 7 дней бесплатно</p>
    </div>
  `
  document.body.appendChild(overlay)
  requestAnimationFrame(() => overlay.classList.add('open'))
}

window._pwSelectPlan = function(id) {
  _selectedPlan = id
  document.querySelectorAll('.pw-plan').forEach(el => {
    el.classList.toggle('selected', el.dataset.plan === id)
  })
}

window._pwBuy = function() {
  const plan = PLANS.find(p => p.id === _selectedPlan)
  if (!plan) return
  // Option 1: open Telegram bot for payment (existing flow)
  const tgUrl = 'https://t.me/IQBarakahBot?start=pay_' + plan.id
  window.open(tgUrl, '_blank')
  // TODO: Option 2: direct YooKassa widget when backend is ready
}
