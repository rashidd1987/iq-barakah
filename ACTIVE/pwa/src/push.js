// Web Push Notifications
// Uses browser Notification API + Service Worker for scheduling

export async function requestPushPermission() {
  if (!('Notification' in window)) return 'unsupported'
  if (Notification.permission === 'granted') return 'granted'
  if (Notification.permission === 'denied') return 'denied'
  const result = await Notification.requestPermission()
  return result
}

export function isPushGranted() {
  return 'Notification' in window && Notification.permission === 'granted'
}

// Schedule a local notification via Service Worker
export async function scheduleNotification({ title, body, tag, delayMs = 0 }) {
  if (!isPushGranted()) return
  if (!('serviceWorker' in navigator)) return
  const reg = await navigator.serviceWorker.ready
  // Use showNotification for immediate; for scheduled we store in SW
  if (delayMs <= 0) {
    reg.showNotification(title, { body, tag, icon: '/icons/icon-192.svg', badge: '/icons/icon-192.svg' })
  } else {
    // Store in localStorage — SW background sync picks up on next wake
    const key = `iq_sched_notif_${tag}`
    localStorage.setItem(key, JSON.stringify({ title, body, tag, fireAt: Date.now() + delayMs }))
  }
}

// Called from main.js after enterApp — set up daily habit reminder
export function initDailyReminder() {
  if (!isPushGranted()) return
  const savedTime = localStorage.getItem('iq_remind_time') || '20:00'
  _scheduleDailyAt(savedTime)
}

function _scheduleDailyAt(hhmm) {
  const [hh, mm] = hhmm.split(':').map(Number)
  const now = new Date()
  const fire = new Date()
  fire.setHours(hh, mm, 0, 0)
  if (fire <= now) fire.setDate(fire.getDate() + 1)
  const delay = fire - now

  clearTimeout(window._pushTimer)
  window._pushTimer = setTimeout(() => {
    scheduleNotification({
      title: '🌙 Время трекера',
      body: 'Отметь привычки за сегодня — не прерывай стрик!',
      tag: 'daily-tracker',
    })
    _scheduleDailyAt(hhmm) // reschedule next day
  }, delay)
}

// Settings: update reminder time
export function setReminderTime(hhmm) {
  localStorage.setItem('iq_remind_time', hhmm)
  _scheduleDailyAt(hhmm)
}

export function getReminderTime() {
  return localStorage.getItem('iq_remind_time') || '20:00'
}
