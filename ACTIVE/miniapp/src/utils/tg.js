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

export function checkHomeScreenStatus(callback) {
  if (!tg?.checkHomeScreenStatus || (tg.isVersionAtLeast && !tg.isVersionAtLeast('8.0'))) {
    callback('unsupported')
    return
  }
  try {
    tg.checkHomeScreenStatus(callback)
  } catch {
    callback('unsupported')
  }
}

export function addToHomeScreen() {
  if (!tg?.addToHomeScreen || (tg.isVersionAtLeast && !tg.isVersionAtLeast('8.0'))) return false
  try {
    tg.addToHomeScreen()
    return true
  } catch {
    return false
  }
}

export function cloudGet(key, cb) {
  tg?.CloudStorage?.getItem(key, cb)
}

export function cloudSet(key, value) {
  tg?.CloudStorage?.setItem(key, value)
}
