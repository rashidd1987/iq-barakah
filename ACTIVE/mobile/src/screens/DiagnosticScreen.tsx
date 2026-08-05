import { Ionicons } from '@expo/vector-icons'
import React, { useMemo, useState } from 'react'
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { useTheme } from '../context/ThemeContext'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { api } from '../utils/api'

// Ported 1:1 from bot_v2/handlers/korablik.py (the "Кораблик" — 7-section ship
// diagnostic) so the app onboarding matches what students already know from the bot.
// Only the ending differs: the bot pitches tariffs here, the app continues into
// VisionScreen since the person is already an enrolled student.

interface Option {
  label: string
  score: 0 | 1 | 2 | 3
}

interface Question {
  title: string
  text: string
  opts: Option[]
}

const QUESTIONS: Question[] = [
  {
    title: 'Вера и намерение',
    text: 'Есть ли у тебя ощущение, что живёшь с намерением — знаешь зачем и ради чего?',
    opts: [
      { label: '😶 Нет, живу как идёт', score: 0 },
      { label: '🌧 Иногда чувствую — потом теряю', score: 1 },
      { label: '🌤 В целом есть внутренняя опора', score: 2 },
      { label: '☀️ Да, каждый день осознанно', score: 3 },
    ],
  },
  {
    title: 'Время и утро',
    text: 'Как начинается твой день?',
    opts: [
      { label: '📱 Сразу в телефон — и так до вечера', score: 0 },
      { label: '🌀 Встаю, но без цели и ритма', score: 1 },
      { label: '☀️ Есть что-то стабильное по утрам', score: 2 },
      { label: '🌟 Утро — якорь всего моего дня', score: 3 },
    ],
  },
  {
    title: 'Цели и движение',
    text: 'Ты движешься к тому, чего хочешь?',
    opts: [
      { label: '😔 Цели есть — движения нет', score: 0 },
      { label: '🔄 Стартую и быстро останавливаюсь', score: 1 },
      { label: '📈 Двигаюсь, но нестабильно', score: 2 },
      { label: '🎯 Есть курс — и я его держу', score: 3 },
    ],
  },
  {
    title: 'Семья и отношения',
    text: 'Как ты присутствуешь в жизни близких?',
    opts: [
      { label: '🏃 Постоянно в хаосе — не до них', score: 0 },
      { label: '📱 Я рядом, но мыслями не здесь', score: 1 },
      { label: '❤️ Стараюсь быть лучше', score: 2 },
      { label: '🏠 Есть тепло, порядок и присутствие', score: 3 },
    ],
  },
  {
    title: 'Деньги и дело',
    text: 'Как обстоят дела с работой и финансами?',
    opts: [
      { label: '😰 Постоянный стресс и нехватка', score: 0 },
      { label: '⚖️ Хватает, но нет роста', score: 1 },
      { label: '📊 Есть движение вперёд', score: 2 },
      { label: '💎 Чувствую баракат в своём деле', score: 3 },
    ],
  },
  {
    title: 'Здоровье и энергия',
    text: 'Как у тебя с энергией и телом?',
    opts: [
      { label: '😴 Хроническая усталость', score: 0 },
      { label: '⚡ Бывают хорошие дни', score: 1 },
      { label: '💪 В целом держусь', score: 2 },
      { label: '🌿 Слежу за телом — это мой инструмент', score: 3 },
    ],
  },
  {
    title: 'Внутренний мир и смысл',
    text: 'Есть ли у тебя ощущение смысла и покоя?',
    opts: [
      { label: '😶 Пустота — зачем всё это', score: 0 },
      { label: '🌧 Иногда теряюсь', score: 1 },
      { label: '🌤 В целом есть внутренняя опора', score: 2 },
      { label: '☀️ Живу с ощущением пути и цели', score: 3 },
    ],
  },
]

const BREAKDOWN: Record<string, Record<number, { icon: string; desc: string; step: string | null }>> = {
  'Вера и намерение': {
    0: { icon: '🔴', desc: 'Ты живёшь скорее по инерции, чем по намерению. Это не слабость — просто никто не показал как иначе.', step: 'Начать день с одного осознанного намерения' },
    1: { icon: '🟡', desc: 'Намерение иногда есть — но держится недолго. Важно создать якорь, который будет возвращать.', step: 'Записывать ният каждое утро — одним предложением' },
    2: { icon: '🟢', desc: 'Есть внутренняя опора. Теперь важно углубить её и сделать ежедневной практикой.', step: 'Углубить через программу' },
    3: { icon: '✨', desc: 'Хвала Аллаху — ты живёшь осознанно. Это основа всего.', step: null },
  },
  'Время и утро': {
    0: { icon: '🔴', desc: 'Утро уходит в телефон — и день уже потерян. Один якорь с утра меняет всё.', step: 'Одно действие до телефона — каждое утро' },
    1: { icon: '🟡', desc: 'Ты встаёшь, но без курса. День управляет тобой, а не ты днём.', step: 'Определить одно утреннее действие и делать его 7 дней' },
    2: { icon: '🟢', desc: 'Есть ритм по утрам. Нужно сделать его более осознанным.', step: 'Добавить намерение к утреннему ритуалу' },
    3: { icon: '✨', desc: 'Утро — якорь. Это уже меняет качество всего дня.', step: null },
  },
  'Цели и движение': {
    0: { icon: '🔴', desc: 'Цели есть — системы нет. Без системы даже сильный человек топчется на месте.', step: 'Один маленький шаг в день — не список, а один шаг' },
    1: { icon: '🟡', desc: 'Ты стартуешь — но не держишь. Нужна не мотивация, а ритм.', step: 'Выбрать одну цель и делать шаг каждый день 2 недели' },
    2: { icon: '🟢', desc: 'Есть движение, но нестабильно. Нужна система удержания.', step: 'Добавить вечерний отчёт: сделал шаг или нет' },
    3: { icon: '✨', desc: 'Держишь курс — это редкость. Теперь важна глубина.', step: null },
  },
  'Семья и отношения': {
    0: { icon: '🔴', desc: 'Хаос вытесняет присутствие. Близкие чувствуют твоё отсутствие, даже когда ты рядом.', step: '15 минут без телефона с близкими — каждый день' },
    1: { icon: '🟡', desc: 'Ты рядом — но не полностью здесь. Присутствие важнее времени.', step: 'Один разговор в день — глаза в глаза, без экрана' },
    2: { icon: '🟢', desc: 'Ты стараешься быть лучше. Нужно перейти от намерения к системе.', step: 'Семейный ритуал — одно действие каждую неделю' },
    3: { icon: '✨', desc: 'Есть тепло и порядок. Это фундамент.', step: null },
  },
  'Деньги и дело': {
    0: { icon: '🔴', desc: 'Стресс вокруг денег забирает энергию на всё остальное. Это замкнутый круг — и из него есть выход.', step: 'Прояснить: где утекает, где можно добавить — один пункт' },
    1: { icon: '🟡', desc: 'Хватает, но нет роста. Дело работает, но без стратегии.', step: 'Один шаг в неделю по развитию дела' },
    2: { icon: '🟢', desc: 'Движение есть. Нужно добавить систему и намерение.', step: 'Соединить дело с миссией — зачем это, кроме денег' },
    3: { icon: '✨', desc: 'Баракат в деле — это видно. Теперь масштаб и служение.', step: null },
  },
  'Здоровье и энергия': {
    0: { icon: '🔴', desc: 'Хроническая усталость — это сигнал, не норма. Тело говорит: что-то нужно изменить.', step: 'Одно действие для тела каждый день — даже 10 минут' },
    1: { icon: '🟡', desc: 'Хорошие дни есть — но нет стабильности. Энергия нужна для всего остального.', step: 'Сон и подъём в одно время — 5 дней подряд' },
    2: { icon: '🟢', desc: 'В целом держишься. Добавь осознанность к заботе о теле.', step: 'Отслеживать энергию: что даёт, что забирает' },
    3: { icon: '✨', desc: 'Тело — инструмент, и ты за ним следишь. Это редкость.', step: null },
  },
  'Внутренний мир и смысл': {
    0: { icon: '🔴', desc: 'Ощущение пустоты — это не конец. Это сигнал: что-то важное ждёт, чтобы его открыли.', step: 'Один разговор с собой: чего я на самом деле хочу' },
    1: { icon: '🟡', desc: 'Иногда теряешься — и это нормально. Важно знать, как возвращаться.', step: 'Вечерний вопрос: за что я благодарен сегодня' },
    2: { icon: '🟢', desc: 'Опора есть. Нужно сделать её более осознанной и глубокой.', step: 'Найти то, что возвращает к смыслу — и делать это регулярно' },
    3: { icon: '✨', desc: 'Живёшь с ощущением пути. Это самое ценное.', step: null },
  },
}

interface Props {
  onContinue: () => void
}

export default function DiagnosticScreen({ onContinue }: Props) {
  const { colors, isDark } = useTheme()
  const styles = useMemo(() => createStyles(colors, isDark), [colors, isDark])
  const [step, setStep] = useState(0)
  const [scores, setScores] = useState<number[]>([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(false)

  const handleAnswer = (score: number) => {
    const next = [...scores, score]
    setScores(next)
    if (step + 1 < QUESTIONS.length) {
      setStep(step + 1)
    }
  }

  const finished = scores.length === QUESTIONS.length

  const finishDiagnostic = async () => {
    if (saving) return
    setSaving(true)
    setSaveError(false)
    try {
      await api.saveDiagnosticResult(scores)
      onContinue()
    } catch {
      setSaveError(true)
    } finally {
      setSaving(false)
    }
  }

  if (!finished) {
    const q = QUESTIONS[step]
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.eyebrow}>Честный разговор перед стартом</Text>
        <View style={styles.dots}>
          {QUESTIONS.map((_, i) => (
            <View key={i} style={[styles.dot, i === step && styles.dotActive, i < step && styles.dotDone]} />
          ))}
        </View>
        <View style={styles.iconCircle}><Ionicons name="navigate" size={36} color={colors.gold} /></View>
        <Text style={styles.stepCounter}>Отсек {step + 1} из {QUESTIONS.length}</Text>
        <Text style={styles.question}>{q.text}</Text>
        <View style={styles.options}>
          {q.opts.map((o) => (
            <Pressable key={o.label} style={styles.optionCard} onPress={() => handleAnswer(o.score)}>
              <Text style={styles.optionLabel}>{o.label}</Text>
            </Pressable>
          ))}
        </View>
        <View style={styles.privacyRow}><Ionicons name="lock-closed-outline" size={14} color={colors.muted} /><Text style={styles.privacyNote}>Это видишь только ты — здесь никто не оценивает</Text></View>
      </ScrollView>
    )
  }

  const total = scores.reduce((a, b) => a + b, 0)

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>Джазакаллаху хайран за честность 🙏</Text>
      <Text style={styles.mapTitle}>Вот твоя картина</Text>
      <View style={styles.mapCard}>
        {QUESTIONS.map((q, i) => {
          const b = BREAKDOWN[q.title][scores[i]]
          return (
            <View key={q.title} style={styles.mapRow}>
              <View style={styles.mapRowHead}>
                <Text style={styles.mapIcon}>{b.icon}</Text>
                <Text style={styles.mapLabel}>{q.title}</Text>
              </View>
              <Text style={styles.mapDesc}>{b.desc}</Text>
              {b.step && <Text style={styles.mapStep}>→ {b.step}</Text>}
            </View>
          )
        })}
      </View>
      <Text style={styles.totalNote}>Итого: {total} из 21</Text>
      {saveError && (
        <Text style={styles.saveError}>Не удалось сохранить уровень. Проверь интернет и попробуй ещё раз.</Text>
      )}
      <Pressable style={[styles.continueButton, saving && styles.continueButtonDisabled]} onPress={finishDiagnostic}>
        {saving ? (
          <ActivityIndicator color={colors.onPrimary} />
        ) : (
          <Text style={styles.continueButtonText}>Сохранить и продолжить</Text>
        )}
      </Pressable>
    </ScrollView>
  )
}

const createStyles = (colors: ThemeColors, isDark: boolean) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 24, paddingTop: 56, flexGrow: 1, justifyContent: 'center' },
  eyebrow: { fontSize: 13, fontWeight: '600', color: colors.gold, marginBottom: 16, textAlign: 'center' },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 6, marginBottom: 24, flexWrap: 'wrap' },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.border },
  dotActive: { backgroundColor: colors.g2, width: 22 },
  dotDone: { backgroundColor: colors.g3 },
  iconCircle: {
    alignSelf: 'center',
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: colors.gpale,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  stepCounter: { fontSize: 13, fontWeight: '600', color: colors.muted, textAlign: 'center', marginBottom: 12 },
  question: {
    fontSize: 21,
    fontWeight: '800',
    color: isDark ? colors.goldpale : colors.g1,
    textAlign: 'center',
    marginBottom: 32,
    lineHeight: 30,
    textShadowColor: isDark ? 'rgba(0, 0, 0, 0.35)' : 'transparent',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: isDark ? 2 : 0,
  },
  options: { gap: 12 },
  optionCard: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 16,
    alignItems: 'center', borderWidth: 1, borderColor: colors.border,
    ...shadow.card,
  },
  optionLabel: { fontSize: 15, lineHeight: 21, fontWeight: '600', color: colors.text },
  privacyRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 6, marginTop: 24 },
  privacyNote: { fontSize: 12, color: colors.muted, textAlign: 'center', flexShrink: 1 },
  mapTitle: { fontSize: 22, fontWeight: '800', color: colors.g1, textAlign: 'center', marginBottom: 20 },
  mapCard: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 16,
    marginBottom: 16,
    ...shadow.card,
  },
  mapRow: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  mapRowHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 4 },
  mapIcon: { fontSize: 18, marginRight: 8 },
  mapLabel: { fontSize: 14, fontWeight: '700', color: colors.text },
  mapDesc: { fontSize: 13, color: colors.sub, lineHeight: 19 },
  mapStep: { fontSize: 12, color: colors.g2, fontWeight: '600', marginTop: 4 },
  totalNote: { fontSize: 12, color: colors.muted, textAlign: 'center', marginBottom: 24 },
  saveError: { color: colors.danger, fontSize: 13, fontWeight: '600', textAlign: 'center', marginBottom: 12 },
  continueButton: {
    backgroundColor: colors.g2,
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: radius.button,
    alignSelf: 'center',
  },
  continueButtonDisabled: { opacity: 0.7 },
  continueButtonText: { color: colors.onPrimary, fontSize: 16, fontWeight: '600' },
  })
}
