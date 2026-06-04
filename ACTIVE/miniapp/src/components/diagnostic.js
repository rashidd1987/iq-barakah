import { haptic, sendData } from '../utils/tg.js'
import { lsSet } from '../utils/storage.js'

// ── Вопросы (новая диагностика потенциала) ──────────────────────────────────
const QS = [
  {q:'Как обычно начинается твой день?',
   opts:['Поздно, сразу в телефон','Рано, но без цели','Есть ритуал','Осознанно, с намерением']},
  {q:'Есть ли у тебя контроль над своим временем?',
   opts:['День управляет мной','Иногда получается','В целом да','Да, я веду день']},
  {q:'Что происходит с твоими целями?',
   opts:['Есть, но движения нет','Стартую и сдаюсь','Нестабильно','Держу курс, даже в трудные дни']},
  {q:'Как справляешься, когда всё идёт не так?',
   opts:['Теряюсь и откладываю','С трудом','Возвращаюсь к плану','Есть своя система']},
  {q:'Как проводишь вечер?',
   opts:['В телефоне — время уходит','Смотрю что сделал','Анализирую день','Итог + план на завтра']},
  {q:'Как у тебя с внутренним покоем?',
   opts:['Постоянная тревога','Бывают хорошие дни','В основном спокоен','Есть ощущение опоры']},
  {q:'Что происходит с семьёй и близкими?',
   opts:['Хаос','Я рядом, но не здесь','Стараюсь быть лучше','Есть порядок и присутствие']},
  {q:'Чего ты хочешь для себя?',
   opts:['Перестать уставать','Вернуть ритм','Построить систему','Служить и оставить след']}
]

// ── Результаты ────────────────────────────────────────────────────────────────
const RS = [
  {pct:22, word:'Начало пути', levelKey:'А', sp:[15,20,18,12],
   nt:'Ты чувствуешь, что топчешься на месте',
   np:'Утро начинается с телефона. Цели есть — движения нет. Дни похожи один на другой.',
   at:'Ты получаешь первый стабильный ритм',
   ap:'Ясное утро. Конкретный план на день. Ощущение, что жизнь под контролем. Не идеально — но твёрдо.'},
  {pct:40, word:'Пробуждение', levelKey:'А', sp:[35,38,30,28],
   nt:'Есть попытки, но нет системы',
   np:'Ты стартуешь — и срываешься. Мотивация приходит волнами. Что-то важное постоянно откладывается.',
   at:'Ты строишь первую рабочую систему',
   ap:'Появляется якорь утра, вечерний разбор. Срывы случаются — но ты умеешь возвращаться.'},
  {pct:58, word:'Рост', levelKey:'Б', sp:[55,60,50,52],
   nt:'Основа есть — но чего-то важного не хватает',
   np:'Ты дисциплинирован, но что-то ускользает. Жизнь работает — без ощущения смысла.',
   at:'Ты соединяешь продуктивность со смыслом',
   ap:'Время, семья, дело и внутренний мир начинают работать вместе. Каждый день — движение, а не список задач.'},
  {pct:76, word:'Глубина', levelKey:'В', sp:[72,75,68,70],
   nt:'Ты живёшь хорошо, но знаешь — можно больше',
   np:'Система есть. Ты чувствуешь плато. Следующий уровень требует другой глубины и окружения.',
   at:'Ты выходишь на уровень, где ведёшь других',
   ap:'Более глубокая работа над характером, семьёй и служением. Ты создаёшь среду роста.'}
]

const SPHERES = [{icon:'🌅',name:'Утро'},{icon:'🎯',name:'Цели'},{icon:'❤️',name:'Семья'},{icon:'🧘',name:'Покой'}]

let cur = 0, ans = new Array(8).fill(null)

// ── Public API ────────────────────────────────────────────────────────────────
export function openDiag() {
  cur = 0; ans = new Array(8).fill(null)
  const ov = document.getElementById('diag-overlay')
  if (ov) ov.classList.remove('hidden')
  _showStep('quiz')
  _renderQ()
}

export function closeDiag() {
  document.getElementById('diag-overlay')?.classList.add('hidden')
}

export function initDiagnostic(onFinish) {
  document.getElementById('diag-overlay')?.addEventListener('click', e => {
    if (e.target === e.currentTarget) { haptic(); closeDiag() }
  })
  document.getElementById('dq-back')?.addEventListener('click', () => {
    haptic()
    if (cur === 0) { closeDiag(); return }
    cur--; _renderQ()
  })
  document.getElementById('dq-next')?.addEventListener('click', () => {
    haptic()
    if (ans[cur] === null) return
    if (cur === QS.length - 1) { _calcResult(onFinish); return }
    cur++; _renderQ()
  })
  document.getElementById('btn-finish-diag')?.addEventListener('click', () => {
    haptic('success'); closeDiag()
    if (onFinish) onFinish()
  })
}

// ── Internal ──────────────────────────────────────────────────────────────────
function _showStep(id) {
  document.querySelectorAll('.diag-step').forEach(s => s.classList.remove('active'))
  document.getElementById('ds-' + id)?.classList.add('active')
}

function _renderQ() {
  const q = QS[cur]
  // Progress
  const pct = Math.round((cur + 1) / QS.length * 100)
  const fill = document.getElementById('dq-prog-fill')
  if (fill) fill.style.width = pct + '%'
  const frac = document.getElementById('dq-frac')
  if (frac) frac.textContent = (cur + 1) + ' / ' + QS.length

  // Question text
  const qt = document.getElementById('dq-text')
  if (qt) qt.textContent = q.q

  // Options
  const og = document.getElementById('dq-opts')
  if (!og) return
  og.innerHTML = q.opts.map((o, i) => `
    <button class="dq-opt${ans[cur] === i ? ' sel' : ''}" data-i="${i}">
      <span class="dq-opt-num">${i + 1}</span>
      <span class="dq-opt-txt">${o}</span>
      <span class="dq-opt-check">✓</span>
    </button>`).join('')

  og.querySelectorAll('.dq-opt').forEach(btn => {
    btn.addEventListener('click', () => {
      haptic()
      ans[cur] = parseInt(btn.dataset.i)
      og.querySelectorAll('.dq-opt').forEach(b => b.classList.remove('sel'))
      btn.classList.add('sel')
      const nx = document.getElementById('dq-next')
      if (nx) { nx.disabled = false }
      // Auto-advance after 400ms
      setTimeout(() => {
        if (cur === QS.length - 1) { _calcResult(null) }
        else { cur++; _renderQ() }
      }, 380)
    })
  })

  const nx = document.getElementById('dq-next')
  if (nx) {
    nx.disabled = ans[cur] === null
    nx.textContent = cur === QS.length - 1 ? 'Узнать потенциал →' : 'Дальше →'
  }
  const bk = document.getElementById('dq-back')
  if (bk) bk.style.opacity = cur === 0 ? '0.3' : '1'
}

function _calcResult(onFinish) {
  const total = ans.reduce((s, v, i) => s + (v !== null ? v : 0), 0)
  const ratio = total / (QS.length * 3)
  const ri = ratio < 0.25 ? 0 : ratio < 0.5 ? 1 : ratio < 0.75 ? 2 : 3
  const R = RS[ri]

  lsSet('level', R.levelKey)
  lsSet('diag_done', '1')

  _showResult(R, onFinish)
}

function _showResult(R, onFinish) {
  _showStep('result')

  // Ring animation
  const rfg = document.getElementById('dr-ring-fg')
  const rpct = document.getElementById('dr-pct')
  const rword = document.getElementById('dr-word')
  if (rfg) {
    const circ = 502
    let n = 0, target = R.pct
    const step = Math.max(1, Math.ceil(target / 50))
    const tm = setInterval(() => {
      n = Math.min(n + step, target)
      if (rpct) rpct.textContent = n + '%'
      rfg.style.strokeDashoffset = circ * (1 - n / 100)
      if (n >= target) clearInterval(tm)
    }, 30)
  }
  if (rword) rword.textContent = R.word

  // Spheres
  const spheresEl = document.getElementById('dr-spheres')
  if (spheresEl) {
    spheresEl.innerHTML = SPHERES.map((s, i) => `
      <div class="dr-sphere">
        <div class="dr-sphere-icon">${s.icon}</div>
        <div class="dr-sphere-name">${s.name}</div>
        <div class="dr-sphere-bar"><div class="dr-sphere-fill" id="dsf${i}"></div></div>
      </div>`).join('')
    setTimeout(() => {
      SPHERES.forEach((_, i) => {
        const el = document.getElementById('dsf' + i)
        if (el) el.style.width = R.sp[i] + '%'
      })
    }, 400)
  }

  // Panels
  const ntEl = document.getElementById('dr-now-title')
  const npEl = document.getElementById('dr-now-text')
  const atEl = document.getElementById('dr-after-title')
  const apEl = document.getElementById('dr-after-text')
  if (ntEl) ntEl.textContent = R.nt
  if (npEl) npEl.textContent = R.np
  if (atEl) atEl.textContent = R.at
  if (apEl) apEl.textContent = R.ap

  // Finish button
  const finBtn = document.getElementById('btn-finish-diag')
  if (finBtn) {
    finBtn.onclick = () => {
      haptic('success')
      sendData({ action: 'diag_complete', level: R.levelKey, pct: R.pct, word: R.word })
      closeDiag()
      if (onFinish) onFinish()
    }
  }
}
