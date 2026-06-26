// PWA stub — replaces Telegram WebApp calls with native equivalents

export function haptic() {}
export function sendData() {}
export function openLink(url) { window.open(url, '_blank') }

export function getTgUser() {
  // В PWA берём пользователя из localStorage (сохраняется после логина)
  try { return JSON.parse(localStorage.getItem('iq_user')) } catch { return null }
}

export function cloudGet(key, cb) {
  try { cb(null, localStorage.getItem('iq_cloud_' + key)) } catch { cb(null, null) }
}

export function cloudSet(key, value) {
  localStorage.setItem('iq_cloud_' + key, value)
}
