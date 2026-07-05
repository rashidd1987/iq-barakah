import React, { useState } from 'react'
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { colors, radius, shadow } from '../theme/colors'

type Severity = 'red' | 'yellow' | 'green'

interface Option {
  label: string
  severity: Severity
}

interface Question {
  key: string
  question: string
  options: Option[]
  mapLabel: string
  mapIcon: string
}

const QUESTIONS: Question[] = [
  {
    key: 'namaz',
    question: 'Сколько раз за последнюю неделю ты по-настоящему был в намазе, а не просто механически его выполнил?',
    options: [
      { label: '0-1 раз', severity: 'red' },
      { label: '2-4 раза', severity: 'yellow' },
      { label: '5-7 раз', severity: 'green' },
    ],
    mapLabel: 'Осознанность в намазе',
    mapIcon: '🕌',
  },
  {
    key: 'phone',
    question: 'Сколько раз в день ты берёшь телефон, не задумываясь, зачем?',
    options: [
      { label: '30+ раз, почти на автомате', severity: 'red' },
      { label: '10-30 раз', severity: 'yellow' },
      { label: 'Меньше 10, обычно осознанно', severity: 'green' },
    ],
    mapLabel: 'Контроль над вниманием',
    mapIcon: '📱',
  },
  {
    key: 'family',
    question: 'Когда ты последний раз был с семьёй по-настоящему, не думая о делах?',
    options: [
      { label: 'Не помню, когда в последний раз', severity: 'red' },
      { label: 'На этой неделе', severity: 'yellow' },
      { label: 'Сегодня', severity: 'green' },
    ],
    mapLabel: 'Присутствие с семьёй',
    mapIcon: '🏠',
  },
]

const SEVERITY_DOT: Record<Severity, string> = { red: '🔴', yellow: '🟡', green: '🟢' }

function synthesize(answers: Severity[]): string {
  const reds = answers.filter((a) => a === 'red').length
  if (reds >= 2) {
    return 'Ты сейчас в основном на автопилоте — это не приговор, а точная отправная точка. Система нужна не потому, что ты слаб, а потому, что даже сильная воля не заменяет структуру.'
  }
  if (reds === 1) {
    return 'Есть опоры, но есть и трещины. Без системы именно они обычно и подводят первыми.'
  }
  return 'Ты уже держишь многое — но осознанность без структуры редко живёт дольше пары недель. Система закрепит то, что уже есть.'
}

interface Props {
  onContinue: () => void
}

export default function DiagnosticScreen({ onContinue }: Props) {
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<Severity[]>([])

  const handleAnswer = (severity: Severity) => {
    const next = [...answers, severity]
    setAnswers(next)
    if (step + 1 < QUESTIONS.length) {
      setStep(step + 1)
    }
    // "seen_diagnostic" is persisted by the parent navigator once the whole
    // onboarding (diagnosis + vision) completes — not here, so a killed app
    // mid-flow doesn't skip the vision screen on next launch.
  }

  const finished = answers.length === QUESTIONS.length

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
        <View style={styles.iconCircle}>
          <Text style={styles.iconCircleText}>{q.mapIcon}</Text>
        </View>
        <Text style={styles.stepCounter}>Вопрос {step + 1} из {QUESTIONS.length}</Text>
        <Text style={styles.question}>{q.question}</Text>
        <View style={styles.options}>
          {q.options.map((o) => (
            <Pressable key={o.label} style={styles.optionCard} onPress={() => handleAnswer(o.severity)}>
              <Text style={styles.optionLabel}>{o.label}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={styles.privacyNote}>Это видишь только ты — здесь никто не оценивает</Text>
      </ScrollView>
    )
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>Твоя карта прямо сейчас</Text>
      <View style={styles.mapCard}>
        {QUESTIONS.map((q, i) => (
          <View key={q.key} style={styles.mapRow}>
            <Text style={styles.mapIcon}>{q.mapIcon}</Text>
            <Text style={styles.mapLabel}>{q.mapLabel}</Text>
            <Text style={styles.mapDot}>{SEVERITY_DOT[answers[i]]}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.reflection}>{synthesize(answers)}</Text>
      <Pressable style={styles.continueButton} onPress={onContinue}>
        <Text style={styles.continueButtonText}>Посмотреть, кем ты станешь</Text>
      </Pressable>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 24, paddingTop: 56, flexGrow: 1, justifyContent: 'center' },
  eyebrow: { fontSize: 13, fontWeight: '600', color: colors.gold, marginBottom: 16, textAlign: 'center' },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: 8, marginBottom: 24 },
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
  iconCircleText: { fontSize: 38 },
  stepCounter: { fontSize: 13, fontWeight: '600', color: colors.muted, textAlign: 'center', marginBottom: 12 },
  question: { fontSize: 20, fontWeight: '700', color: colors.g1, textAlign: 'center', marginBottom: 32, lineHeight: 28 },
  options: { gap: 12 },
  privacyNote: { fontSize: 12, color: colors.muted, textAlign: 'center', marginTop: 24 },
  optionCard: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 16,
    alignItems: 'center',
    ...shadow.card,
  },
  optionLabel: { fontSize: 16, fontWeight: '600', color: colors.text },
  mapCard: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 16,
    marginBottom: 20,
    ...shadow.card,
  },
  mapRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  mapIcon: { fontSize: 20, marginRight: 12 },
  mapLabel: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.text },
  mapDot: { fontSize: 16 },
  reflection: { fontSize: 14, color: colors.sub, textAlign: 'center', lineHeight: 21, marginBottom: 28 },
  continueButton: {
    backgroundColor: colors.g2,
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: radius.button,
    alignSelf: 'center',
  },
  continueButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
})
