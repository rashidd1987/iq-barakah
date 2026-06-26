export const tg = window.Telegram?.WebApp ?? null

export function initTg() {
  if (!tg) return
  tg.ready()
  tg.expand()
  tg.enableClosingConfirmation()
}

export function haptic(type = 'impact') {
  if (!tg?.HapticFeedback) return
  type === 'impact'
    ? tg.HapticFeedback.impactOccurred('light')
    : tg.HapticFeedback.notificationOccurred(type)
}

export function sendData(payload) {
  if (tg) tg.sendData(JSON.stringify(payload))
}

export function openLink(url) {
  if (tg) tg.openLink(url)
  else window.open(url, '_blank')
}

export function getTgUser() {
  return tg?.initDataUnsafe?.user ?? null
}

export function cloudGet(key, cb) {
  tg?.CloudStorage?.getItem(key, cb)
}

export function cloudSet(key, value) {
  tg?.CloudStorage?.setItem(key, value)
}
