const SUPPORTED = ['ru', 'en', 'ar', 'de', 'tr', 'id', 'ur', 'bn', 'fr', 'ms']
const RTL = new Set(['ar', 'ur'])

const TEXT = {
  ru: {
    home: 'Главная',
    tracker: 'Трекер',
    lessons: 'Уроки',
    wheel: 'Баланс',
    ship: 'Корабль',
  },
  en: {
    home: 'Home',
    tracker: 'Tracker',
    lessons: 'Lessons',
    wheel: 'Balance',
    ship: 'Ship',
  },
  ar: {
    home: 'الرئيسية',
    tracker: 'المتابعة',
    lessons: 'الدروس',
    wheel: 'التوازن',
    ship: 'السفينة',
  },
  de: {
    home: 'Start',
    tracker: 'Tracker',
    lessons: 'Lektionen',
    wheel: 'Balance',
    ship: 'Schiff',
  },
}

let currentLang = 'ru'

export function initI18n() {
  const params = new URLSearchParams(window.location.search)
  const fromUrl = params.get('lang')
  const saved = localStorage.getItem('iq_lang')
  currentLang = normalizeLang(fromUrl || saved || window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code)
  localStorage.setItem('iq_lang', currentLang)

  document.documentElement.lang = currentLang
  document.documentElement.dir = RTL.has(currentLang) ? 'rtl' : 'ltr'
  applyI18n()
}

export function lang() {
  return currentLang
}

export function t(key) {
  return TEXT[currentLang]?.[key] || TEXT.ru[key] || key
}

function normalizeLang(value) {
  const code = String(value || 'ru').toLowerCase().split('-')[0]
  return SUPPORTED.includes(code) ? code : 'ru'
}

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n)
  })
}
