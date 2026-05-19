export const NAMAZ = [
  { id: 'fajr',    label: 'Фаджр', icon: '🌅' },
  { id: 'zuhr',    label: 'Зухр',  icon: '☀️' },
  { id: 'asr',     label: 'Аср',   icon: '🌤' },
  { id: 'maghrib', label: 'Магриб',icon: '🌇' },
  { id: 'isha',    label: 'Иша',   icon: '🌙' },
]

export const DAILY = [
  { id: 'azkar_m', icon: '📿', label: 'Утренний азкар',  sub: '06:00 · Азкары + Фаджр',          streak: 0 },
  { id: 'dhuhr',   icon: '🕛', label: 'Обеденный намаз', sub: '13:30 · Зухр + азкары после',      streak: 0 },
  { id: 'azkar_e', icon: '🌇', label: 'Вечерний азкар',  sub: '20:00 · Азкары + Магриб/Иша',     streak: 0 },
  { id: 'muhasaba',icon: '🌙', label: 'Мухасаба',        sub: '22:00 · 3 вопроса перед сном',     streak: 0 },
  { id: 'quran',   icon: '📖', label: 'Коран',           sub: '1 страница в день',                streak: 0 },
  { id: 'deed',    icon: '🤲', label: 'Доброе дело',     sub: 'Любое благо — запишите',           streak: 0 },
]

export const WEEKLY = [
  { id: 'lesson', icon: '📚', label: 'Урок недели',        sub: 'Пн · 9:00 — бот пришлёт урок и задания' },
  { id: 'call',   icon: '🎙', label: 'Живой созвон',       sub: 'Пт · 14:00 — с основателем IQ Barakah'  },
  { id: 'guest',  icon: '🎤', label: 'Пятничный гость',    sub: 'Пт — шейх, врач или предприниматель'     },
  { id: 'mirror', icon: '📊', label: 'Зеркало прогресса',  sub: 'Каждые 2 нед — авто-отчёт бота'         },
]

export const ONETIME = [
  { id: 'letter', icon: '✉️', label: 'Письмо себе',    sub: 'День нулевой — прочтёшь в конце'        },
  { id: 'anchor', icon: '👥', label: 'Якорный брат',   sub: 'При входе — брат с похожим уровнем'      },
]
