// Export user progress as JSON or CSV

export function exportProgress() {
  const data = _collectData()
  const json = JSON.stringify(data, null, 2)
  _download(`iq-barakah-progress-${_dateStr()}.json`, json, 'application/json')
}

export function exportProgressCSV() {
  const data = _collectData()
  const rows = [['Дата', 'Привычки выполнено', 'Намаз', 'Стрик']]
  Object.entries(data.tracker || {}).forEach(([date, habits]) => {
    const total = Object.keys(habits).length
    const namaz = Object.keys(habits).filter(k => k.startsWith('n_')).length
    rows.push([date, total, namaz, ''])
  })
  const csv = rows.map(r => r.join(',')).join('\n')
  _download(`iq-barakah-tracker-${_dateStr()}.csv`, csv, 'text/csv')
}

function _collectData() {
  const user = _ls('iq_user', {})
  const tracker = _ls('iq_checked', {})
  const wheel = _ls('iq_wheel', {})
  const level = _ls('iq_level', '')
  const week = _ls('iq_currentWeek', 0)
  return {
    exportedAt: new Date().toISOString(),
    user: { name: user.name, email: user.email },
    progress: { level, week },
    tracker,
    wheel,
  }
}

function _ls(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback } catch { return fallback }
}

function _dateStr() {
  return new Date().toISOString().slice(0, 10)
}

function _download(filename, content, mime) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url) }, 100)
}
