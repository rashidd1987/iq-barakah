// Ported from ACTIVE/miniapp/src/data/weeks.js — single source for the 30-step
// global program layout (6 VAKT + 8 + 8 + 8 across levels А/Б/В/Г).
export interface GlobalWeek {
  id: string
  phase: 'vakt' | 's1' | 's2' | 's3'
  num: string
  title: string
  sub: string
  icon: string
}

export const WEEKS: GlobalWeek[] = [
  { id: 'v1', phase: 'vakt', num: 'В1', title: 'Намерение', sub: 'Вернуть ният и понять, куда уходит день', icon: '🌱' },
  { id: 'v2', phase: 'vakt', num: 'В2', title: 'Утро', sub: 'Сделать утро главным якорем ритма', icon: '🌅' },
  { id: 'v3', phase: 'vakt', num: 'В3', title: 'Ритм', sub: 'Планировать день вокруг ритма, а не хаоса', icon: '🏠' },
  { id: 'v4', phase: 'vakt', num: 'В4', title: 'Внимание', sub: 'Ослабить власть телефона и рассеивания', icon: '⏱' },
  { id: 'v5', phase: 'vakt', num: 'В5', title: 'Вечерний отчёт', sub: 'Благодарность, пробоина, следующий шаг', icon: '🌙' },
  { id: 'v6', phase: 'vakt', num: 'В6', title: 'Постоянство', sub: 'Закрепить систему и выбрать следующий уровень', icon: '🏆' },
  { id: 's1_1', phase: 's1', num: 'С1.1', title: 'Тайный разговор', sub: 'Сезон 1 · Шаг 1', icon: '🌱' },
  { id: 's1_2', phase: 's1', num: 'С1.2', title: 'Возвращение домой', sub: 'Сезон 1 · Шаг 2', icon: '🏠' },
  { id: 's1_3', phase: 's1', num: 'С1.3', title: 'Священное пространство', sub: 'Сезон 1 · Шаг 3', icon: '✨' },
  { id: 's1_4', phase: 's1', num: 'С1.4', title: 'Время как свидетель', sub: 'Сезон 1 · Шаг 4', icon: '⏱' },
  { id: 's1_5', phase: 's1', num: 'С1.5', title: 'Кто твой Господь?', sub: 'Сезон 1 · Шаг 5', icon: '📱' },
  { id: 's1_6', phase: 's1', num: 'С1.6', title: 'Нулевой километр', sub: 'Сезон 1 · Шаг 6', icon: '🧹' },
  { id: 's1_7', phase: 's1', num: 'С1.7', title: 'Ты — не мозг в банке', sub: 'Сезон 1 · Шаг 7', icon: '💪' },
  { id: 's1_8', phase: 's1', num: 'С1.8', title: 'Генеральная уборка души', sub: 'Сезон 1 · Шаг 8', icon: '🌿' },
  { id: 's2_1', phase: 's2', num: 'С2.1', title: 'Как шайтан взламывает мозг', sub: 'Сезон 2 · Шаг 1', icon: '🧠' },
  { id: 's2_2', phase: 's2', num: 'С2.2', title: 'Строительство крепости', sub: 'Сезон 2 · Шаг 2', icon: '🏗' },
  { id: 's2_3', phase: 's2', num: 'С2.3', title: 'Сжигание кораблей', sub: 'Сезон 2 · Шаг 3', icon: '🔥' },
  { id: 's2_4', phase: 's2', num: 'С2.4', title: 'Что тяжелее всего на весах?', sub: 'Сезон 2 · Шаг 4', icon: '⚖️' },
  { id: 's2_5', phase: 's2', num: 'С2.5', title: 'Дай плату, пока не высох пот', sub: 'Сезон 2 · Шаг 5', icon: '💼' },
  { id: 's2_6', phase: 's2', num: 'С2.6', title: 'Самый длинный аят', sub: 'Сезон 2 · Шаг 6', icon: '📜' },
  { id: 's2_7', phase: 's2', num: 'С2.7', title: 'Партнёрство с Аллахом', sub: 'Сезон 2 · Шаг 7', icon: '🤝' },
  { id: 's2_8', phase: 's2', num: 'С2.8', title: 'Синдром Атланта', sub: 'Сезон 2 · Шаг 8', icon: '🌍' },
  { id: 's3_1', phase: 's3', num: 'С3.1', title: 'У подножия их ног', sub: 'Сезон 3 · Шаг 1', icon: '👣' },
  { id: 's3_2', phase: 's3', num: 'С3.2', title: 'Оставь войну за порогом', sub: 'Сезон 3 · Шаг 2', icon: '🏠' },
  { id: 's3_3', phase: 's3', num: 'С3.3', title: 'Зеркальные нейроны', sub: 'Сезон 3 · Шаг 3', icon: '👶' },
  { id: 's3_4', phase: 's3', num: 'С3.4', title: 'Кузнец и парфюмер', sub: 'Сезон 3 · Шаг 4', icon: '🌹' },
  { id: 's3_5', phase: 's3', num: 'С3.5', title: 'Король без короны', sub: 'Сезон 3 · Шаг 5', icon: '👑' },
  { id: 's3_6', phase: 's3', num: 'С3.6', title: 'Река и болото', sub: 'Сезон 3 · Шаг 6', icon: '🌊' },
  { id: 's3_7', phase: 's3', num: 'С3.7', title: 'Открытый счёт', sub: 'Сезон 3 · Шаг 7', icon: '📊' },
  { id: 's3_8', phase: 's3', num: 'С3.8', title: 'Точка невозврата', sub: 'Сезон 3 · Шаг 8', icon: '🏛️' },
]

export const PHASE_LABELS: Record<GlobalWeek['phase'], string> = {
  vakt: '🌱 IQ Barakah Старт · Тайм-менеджмент мусульманина (6 шагов)',
  s1: '📗 Сезон 1 · Основание · КТО ты есть (8 шагов)',
  s2: '📘 Сезон 2 · Строительство · КАК ты живёшь (8 шагов)',
  s3: '📙 Сезон 3 · Наследие · ЗАЧЕМ ты живёшь (8 шагов)',
}

// Maps program level letter (А/Б/В/Г, as stored in bot_v2 Participant.level) to its
// 0-based offset into the unified 30-step WEEKS array.
export const LEVEL_OFFSET: Record<string, number> = { А: 0, Б: 6, В: 14, Г: 22 }
export const LEVEL_ICONS: Record<string, string> = { А: '🌱', Б: '📗', В: '📘', Г: '📙' }
export const LEVEL_LABELS: Record<string, string> = { А: 'IQ Barakah Старт', Б: 'Сезон 1', В: 'Сезон 2', Г: 'Сезон 3' }

export const TOTAL_STEPS = WEEKS.length // 30

export function globalWeekIndex(level: string, levelWeek: number): number {
  return (LEVEL_OFFSET[level] ?? 0) + levelWeek
}

// Inverse of globalWeekIndex — needed to call GET /mobile/content/{level}/{week},
// which is keyed per-level (matches bot_v2's storage), not by the global 1-30 index.
export function weekToLevelIndex(globalIndex: number): { level: string; levelWeekIndex: number } {
  if (globalIndex <= 6) return { level: 'А', levelWeekIndex: globalIndex }
  if (globalIndex <= 14) return { level: 'Б', levelWeekIndex: globalIndex - 6 }
  if (globalIndex <= 22) return { level: 'В', levelWeekIndex: globalIndex - 14 }
  return { level: 'Г', levelWeekIndex: globalIndex - 22 }
}
