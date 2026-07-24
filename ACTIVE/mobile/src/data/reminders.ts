export interface DailyReminder {
  text: string
  source: string
}

// Curated from the already reviewed lesson corpus in ACTIVE/pwa/src/data/content.js.
// Keep the source beside every text; never display unattributed religious quotations.
export const DAILY_REMINDERS: DailyReminder[] = [
  {
    text: 'Поистине, дела оцениваются только по намерениям, и каждому человеку — лишь то, что он намеревался обрести.',
    source: 'Сахих аль-Бухари №1 · Сахих Муслим №1907',
  },
  {
    text: 'Самые любимые дела пред Аллахом — самые постоянные, даже если они малы.',
    source: 'Сахих аль-Бухари №6464 · Сахих Муслим №782',
  },
  {
    text: 'Поистине, в поминании Аллаха успокаиваются сердца.',
    source: 'Коран · сура 13 «Ар-Ра’д» · аят 28',
  },
  {
    text: 'Поистине, Аллах с терпеливыми.',
    source: 'Коран · сура 2 «Аль-Бакара» · аят 153',
  },
  {
    text: 'Сильный верующий лучше и любимее для Аллаха, чем слабый верующий — хотя в каждом из них есть благо.',
    source: 'Сахих Муслим №2664',
  },
  {
    text: 'Не уменьшается имущество от садаки.',
    source: 'Сахих Муслим №2588',
  },
  {
    text: 'Аллах помогает рабу, пока раб помогает своему брату.',
    source: 'Сахих Муслим №2699',
  },
]

export function reminderForDate(date = new Date()): DailyReminder {
  const dayNumber = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86_400_000)
  return DAILY_REMINDERS[((dayNumber % DAILY_REMINDERS.length) + DAILY_REMINDERS.length) % DAILY_REMINDERS.length]
}
