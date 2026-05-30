/**
 * stats.js — вычисляет стрик, добрые дела и баракат-баллы из localStorage.
 * Не требует серверных запросов.
 */
import { lsGet } from './storage.js'
import { TASKS } from '../data/tasks.js'

// ── Стрик (дней подряд) ──────────────────────────────────────────────────────
// День «засчитывается», если в трекере отмечено хотя бы 1 привычка.
export function computeStreak() {
  const checked = lsGet('checked', {})
  let streak = 0
  const today = new Date()

  for (let i = 0; i < 365; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const key = d.toISOString().split('T')[0]
    const dayData = checked[key]
    if (dayData && Object.keys(dayData).length > 0) {
      streak++
    } else {
      // Сегодня ещё нет данных — не ломаем стрик за текущий день
      if (i === 0) continue
      break
    }
  }
  return streak
}

// ── Добрые дела ──────────────────────────────────────────────────────────────
// Сумма: записей «доброе дело» в трекере + выполненных заданий по урокам.
export function computeDeeds(level) {
  let count = 0

  // 1) «deed» из ежедневного трекера
  const checked = lsGet('checked', {})
  for (const dayData of Object.values(checked)) {
    if (dayData && dayData['deed']) count++
  }

  // 2) Выполненные задания по урокам
  if (level) {
    const prog = TASKS[level]
    if (prog) {
      prog.forEach((_, weekIdx) => {
        const weekNum = weekIdx + 1
        const state = lsGet(`tasks_${level}_${weekNum}`, {})
        count += Object.values(state).filter(Boolean).length
      })
    }
  }

  return count
}

// ── Баракат-баллы (XP) ───────────────────────────────────────────────────────
// Формула: стрик × 5 + недель_сдано × 50 + добрых_дел × 10
export function computeXP(streak, weeksDone, deeds) {
  return streak * 5 + weeksDone * 50 + deeds * 10
}

// ── Всё сразу ────────────────────────────────────────────────────────────────
export function computeAllStats(level, weeksDone) {
  const streak = computeStreak()
  const deeds  = computeDeeds(level)
  const xp     = computeXP(streak, weeksDone, deeds)
  return { streak, deeds, xp }
}
