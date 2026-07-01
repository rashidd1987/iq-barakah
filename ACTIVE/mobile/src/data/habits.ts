// Habit ids ported from ACTIVE/miniapp/src/data/habits.js — must match bot_v2 TrackerRecord.habits keys exactly.
export interface HabitDef {
  id: string
  label: string
  icon: string
  sub?: string
}

export const NAMAZ: HabitDef[] = [
  { id: 'fajr', label: 'Фаджр', icon: '🌅' },
  { id: 'zuhr', label: 'Зухр', icon: '☀️' },
  { id: 'asr', label: 'Аср', icon: '🌤' },
  { id: 'maghrib', label: 'Магриб', icon: '🌇' },
  { id: 'isha', label: 'Иша', icon: '🌙' },
]

export const DAILY: HabitDef[] = [
  { id: 'azkar_m', icon: '📿', label: 'Утреннее поминание', sub: '06:00 · Азкары (зикр) + Фаджр' },
  { id: 'dhuhr', icon: '🕛', label: 'Обеденный намаз', sub: '13:30 · Зухр + поминание после' },
  { id: 'azkar_e', icon: '🌇', label: 'Вечернее поминание', sub: '20:00 · Азкары + Магриб/Иша' },
  { id: 'muhasaba', icon: '🌙', label: 'Самоотчёт вечера', sub: '22:00 · Мухасаба · 3 вопроса' },
  { id: 'quran', icon: '📖', label: 'Коран', sub: '1 страница в день' },
  { id: 'deed', icon: '🤲', label: 'Доброе дело', sub: 'Любое благо — запишите' },
]

export const WEEKLY: HabitDef[] = [
  { id: 'lesson', icon: '📚', label: 'Урок недели', sub: 'Пн · 9:00 — бот пришлёт урок и задания' },
  { id: 'call', icon: '🎙', label: 'Живой созвон', sub: 'Пт · 14:00 — с основателем IQ Barakah' },
  { id: 'guest', icon: '🎤', label: 'Пятничный гость', sub: 'Пт — шейх, врач или предприниматель' },
  { id: 'mirror', icon: '📊', label: 'Зеркало прогресса', sub: 'Каждые 2 нед — авто-отчёт бота' },
]
