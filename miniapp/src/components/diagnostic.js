import { haptic, sendData } from '../utils/tg.js'
import { lsSet } from '../utils/storage.js'

const QDATA = [
  {q:'Встаёшь на Фаджр?',opts:[['😔','Никогда',0],['🔄','Иногда',1],['✅','Регулярно',2],['⭐','Всегда + тахаджуд',3]]},
  {q:'Читаешь утренние азкары?',opts:[['❌','Не читаю',0],['🔄','Иногда',1],['📖','Не каждый день',2],['✅','Каждый день',3]]},
  {q:'Планируешь свой день?',opts:[['🌊','Живу как идёт',0],['💭','В голове',1],['📝','Иногда пишу',2],['⭐','Фаджр-лист каждый день',3]]},
  {q:'Делаешь мухасабу вечером?',opts:[['❓','Что это?',0],['💭','Иногда',1],['🔄','Пробовал — бросил',2],['✅','Каждый вечер',3]]},
  {q:'Как у тебя с телефоном утром?',opts:[['📱','Телефон управляет мной',0],['🔄','Пытаюсь ограничить',1],['⚖️','Есть правила — срываюсь',2],['✅','Контролирую осознанно',3]]},
  {q:'Читаешь Коран?',opts:[['❌','Не читаю',0],['🌙','По праздникам',1],['📖','Иногда в неделю',2],['✅','Каждый день',3]]},
  {q:'Как твой бизнес или работа?',opts:[['🌀','Полный хаос',0],['⚙️','Без системы',1],['📊','Система есть — нет баракта',2],['✨','Ищу смысл',3]]},
  {q:'Как дела в твоей семье?',opts:[['🏃','Почти не бываю дома',0],['📱','Бываю — но в телефоне',1],['❤️','Уделяю — хочу больше',2],['🏠','Семья — моя крепость',3]]},
]

const WHEEL_LABELS = ['Иман','Время','Привычки','Тело','Бизнес','Характер','Семья','Миссия']
const WHEEL_COLORS = ['#2c5f2d','#c9a84c','#5b8fa8','#e07b39','#7b5ea7','#d4547a','#4a9e8c','#3d7a3e']

const RESULTS = {
  a:{color:'#C0420A',level:'Уровень А — Начинаю с нуля',levelKey:'А',wheel:[1,1,1,2,2,2,2,1],
     intro:'Это честный результат. Точка силы, не слабости.',
     pains:['😔 День управляется обстоятельствами','📱 Телефон — первое что видишь утром','🌙 Фаджр уходит мимо','🔄 Начинаешь с понедельника — срыв через 3-7 дней'],
     path:'➤ Твой старт: ВАКТ — Тайм-менеджмент мусульманина'},
  b:{color:'#0C3D7A',level:'Уровень Б — Иногда практикую',levelKey:'Б',wheel:[3,4,3,3,4,3,3,2],
     intro:'Ты уже на пути. Есть база — намаз бывает, Коран иногда. Но система не держится.',
     pains:['📉 Знаешь как надо — но не делаешь стабильно','🔁 Привычки: неделя хорошо — срыв — стыд','⏰ Утро без системы','🎯 Нет ясности зачем всё это'],
     path:'➤ Твой старт: ВАКТ → IQ Barakah Сезон 1'},
  c:{color:'#1E4D0A',level:'Уровень В — Практикую регулярно',levelKey:'В',wheel:[6,6,6,6,6,6,5,4],
     intro:'МашаАллах! Намаз, азкары, Коран — есть. Но чего-то не хватает.',
     pains:['🔍 Намаз без присутствия','🏔️ Плато — застрял(а)','💰 Бизнес есть — нет баракта','🕊️ Хочешь передать знание — нет инструмента'],
     path:'➤ Твой старт: IQ Barakah Сезон 1 → Сезон 2'},
  d:{color:'#1A3D08',level:'Уровень В+ — Готов к наследию',levelKey:'В',wheel:[8,8,8,8,8,8,8,6],
     intro:'МашаАллах! Практика есть, система есть. Готов(а) к большему.',
     pains:['🌍 Хочешь влиять на Умму — нет структуры','🔗 Достижения заканчиваются на тебе','👑 Ты лидер — без сообщества','🏛️ Хочешь оставить наследие — не знаешь как'],
     path:'➤ Твой старт: Джамаат или Лидер Уммы'},
}

let qCur = 0, qAnsList = new Array(8).fill(null), selectedQuickLevel = null

export function openDiag() {
  qCur = 0; qAnsList = new Array(8).fill(null); selectedQuickLevel = null
  document.getElementById('diag-overlay').classList.remove('hidden')
  showDiagStep('choice')
}

export function closeDiag() {
  document.getElementById('diag-overlay').classList.add('hidden')
}

function showDiagStep(id) {
  document.querySelectorAll('.diag-step').forEach(s => s.classList.remove('active'))
  document.getElementById('ds-' + id).classList.add('active')
}

export function initDiagnostic(onFinish) {
  document.getElementById('btn-quick')?.addEventListener('click', () => { haptic(); showDiagStep('quick') })
  document.getElementById('btn-quiz')?.addEventListener('click', () => {
    haptic(); qCur = 0; qAnsList = new Array(8).fill(null); renderQuiz(); showDiagStep('quiz')
  })
  document.getElementById('btn-back-choice')?.addEventListener('click', () => { haptic(); showDiagStep('choice') })
  document.getElementById('quick-confirm')?.addEventListener('click', () => {
    if (!selectedQuickLevel) return
    haptic('success')
    showResult(RESULTS[selectedQuickLevel], null, onFinish)
  })
  document.querySelectorAll('.lcard').forEach(card => {
    card.addEventListener('click', () => {
      haptic()
      document.querySelectorAll('.lcard').forEach(c => c.classList.remove('selected'))
      card.classList.add('selected')
      selectedQuickLevel = card.dataset.key
      const btn = document.getElementById('quick-confirm')
      btn.disabled = false; btn.style.opacity = '1'
    })
  })
  document.getElementById('qback')?.addEventListener('click', () => {
    haptic()
    if (qCur === 0) { showDiagStep('choice'); return }
    qCur--; renderQuiz()
  })
  document.getElementById('qnext')?.addEventListener('click', () => {
    haptic()
    if (qAnsList[qCur] === null) return
    if (qCur === QDATA.length - 1) { calcResult(onFinish); return }
    qCur++; renderQuiz()
  })
  document.getElementById('btn-finish-diag')?.addEventListener('click', () => {
    haptic('success'); closeDiag()
    if (onFinish) onFinish()
  })
}

function renderQuiz() {
  const q = QDATA[qCur]
  document.getElementById('qprog').innerHTML = QDATA.map((_, i) =>
    `<div class="qpd ${i < qCur ? 'done' : i === qCur ? 'cur' : ''}"></div>`).join('')
  document.getElementById('qnum').textContent = `ВОПРОС ${qCur + 1} ИЗ ${QDATA.length}`
  document.getElementById('qtext').textContent = q.q
  document.getElementById('qopts').innerHTML = q.opts.map(o =>
    `<button class="q-opt${qAnsList[qCur] === o[2] ? ' sel' : ''}" data-score="${o[2]}">
      <span class="oi">${o[0]}</span><span class="ol">${o[1]}</span></button>`).join('')
  document.querySelectorAll('.q-opt').forEach(btn => {
    btn.addEventListener('click', () => {
      haptic()
      qAnsList[qCur] = parseInt(btn.dataset.score)
      document.querySelectorAll('.q-opt').forEach(b => b.classList.remove('sel'))
      btn.classList.add('sel')
      const nx = document.getElementById('qnext')
      nx.disabled = false; nx.style.opacity = '1'
    })
  })
  const nx = document.getElementById('qnext')
  nx.textContent = qCur === QDATA.length - 1 ? 'Узнать результат →' : 'Далее →'
  nx.disabled = qAnsList[qCur] === null; nx.style.opacity = qAnsList[qCur] === null ? '.5' : '1'
  document.getElementById('qback').style.opacity = qCur === 0 ? '.4' : '1'
}

function calcResult(onFinish) {
  const total = qAnsList.reduce((s, a) => s + (a || 0), 0)
  const pct = Math.round(total / (QDATA.length * 3) * 100)
  const key = pct > 75 ? 'd' : pct > 50 ? 'c' : pct > 25 ? 'b' : 'a'
  showResult(RESULTS[key], pct, onFinish)
}

function showResult(R, pct, onFinish) {
  const badge = document.getElementById('res-badge')
  badge.style.background = R.color
  badge.textContent = pct !== null ? pct + '%' : R.levelKey
  document.getElementById('res-level').textContent = R.level
  document.getElementById('res-level').style.color = R.color
  document.getElementById('res-intro').textContent = R.intro
  drawDiagWheel(R.wheel, R.color)
  document.getElementById('wheel-legend').innerHTML = WHEEL_LABELS.map((l, i) =>
    `<span style="font-size:11px;font-weight:600;color:${WHEEL_COLORS[i]};background:${WHEEL_COLORS[i]}18;padding:2px 8px;border-radius:10px;">${l}</span>`).join('')
  document.getElementById('res-pains').innerHTML = R.pains.map(p => `<div class="pain-item">${p}</div>`).join('')
  document.getElementById('res-path').textContent = R.path
  lsSet('level', R.levelKey)
  lsSet('diag_done', '1')
  showDiagStep('result')
}

function drawDiagWheel(vals, color) {
  const N = 8, R = 68, cx = 78, cy = 78
  function pt(i, v) { const a = (i / N) * Math.PI * 2 - Math.PI / 2, r = (v / 10) * R; return [cx + r * Math.cos(a), cy + r * Math.sin(a)] }
  function pf(i)    { const a = (i / N) * Math.PI * 2 - Math.PI / 2; return [cx + R * Math.cos(a), cy + R * Math.sin(a)] }
  let html = ''
  for (let g = 2; g <= 10; g += 2) {
    const gp = Array.from({ length: N }, (_, i) => pt(i, g))
    html += `<polygon points="${gp.map(p => p.join(',')).join(' ')}" fill="none" stroke="#eee" stroke-width="1"/>`
  }
  for (let i = 0; i < N; i++) {
    const [fx, fy] = pf(i)
    html += `<line x1="${cx}" y1="${cy}" x2="${fx}" y2="${fy}" stroke="#ddd" stroke-width="1"/>`
  }
  const poly = vals.map((v, i) => pt(i, v).join(',')).join(' ')
  html += `<polygon points="${poly}" fill="${color}30" stroke="${color}" stroke-width="2"/>`
  document.getElementById('res-wheel').innerHTML = html
}
