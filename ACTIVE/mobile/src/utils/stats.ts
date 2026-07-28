// Ported from ACTIVE/pwa/src/utils/stats.js — same XP formula, but sourced from server
// tracker records (GET /mobile/tracker) instead of localStorage, since progress now lives in bot_v2.

export interface TrackerRecord {
  date: string // YYYY-MM-DD
  habits: { namaz?: Record<string, boolean>; daily?: Record<string, boolean> }
}

function hasAnyHabit(record: TrackerRecord | undefined): boolean {
  if (!record) return false
  const namazDone = Object.values(record.habits.namaz ?? {}).some(Boolean)
  const dailyDone = Object.values(record.habits.daily ?? {}).some(Boolean)
  return namazDone || dailyDone
}

// Streak-shield: one missed day per 7 consecutive days doesn't break the streak
// (same idea as Duolingo's streak freeze) — a single human slip shouldn't wipe out
// weeks of consistency, but skipping still can't go on forever.
export function computeStreak(records: TrackerRecord[]): number {
  const byDate = new Map(records.map((r) => [r.date, r]))
  let streak = 0
  let shieldsAvailable = 1
  let daysSinceShieldReset = 0
  const today = new Date()

  for (let i = 0; i < 365; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    const record = byDate.get(key)
    if (hasAnyHabit(record)) {
      streak++
      daysSinceShieldReset++
      if (daysSinceShieldReset >= 7) {
        shieldsAvailable = 1
        daysSinceShieldReset = 0
      }
    } else if (i === 0) {
      continue // today may not have data yet — don't break the streak on it
    } else if (shieldsAvailable > 0) {
      shieldsAvailable--
      daysSinceShieldReset = 0
    } else {
      break
    }
  }
  return streak
}

export function computeDeeds(records: TrackerRecord[]): number {
  return records.filter((r) => r.habits.daily?.deed).length
}

export function computeXP(streak: number, weeksDone: number, deeds: number): number {
  return streak * 5 + weeksDone * 50 + deeds * 10
}
