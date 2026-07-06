import { NativeStackScreenProps } from '@react-navigation/native-stack'
import React, { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native'
import { HomeStackParamList } from '../navigation/types'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'

// Ported 1:1 from bot_v2/handlers/muhasaba.py — same 3 questions and hadith framing,
// saved into the same muhasaba_logs table so the record is visible whether it was
// answered here or in the Telegram bot.
const QUESTIONS = [
  {
    q: 'Что сегодня получилось?',
    prompt: 'Что сегодня получилось — даже самое маленькое?',
    hint: 'Аллах видит каждое усилие, даже если его не видит никто.',
  },
  {
    q: 'Что далось тяжело?',
    prompt: 'Что далось тяжело — и почему?',
    hint: 'Честность с собой — это уже часть поклонения. Не суди себя, просто замечай.',
  },
  {
    q: 'Что сделаю иначе завтра?',
    prompt: 'Что хочу сделать иначе завтра?',
    hint: 'Одно маленькое намерение — уже шаг вперёд. БисмиЛлях.',
  },
]

type Props = NativeStackScreenProps<HomeStackParamList, 'Muhasaba'>

export default function MuhasabaScreen({ navigation }: Props) {
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState<string[]>(['', '', ''])
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)
  const [streak, setStreak] = useState<number | null>(null)
  const [checkingToday, setCheckingToday] = useState(true)
  const [alreadyDoneToday, setAlreadyDoneToday] = useState(false)

  const checkToday = useCallback(() => {
    setCheckingToday(true)
    api
      .muhasabaStreak()
      .then((res) => setAlreadyDoneToday(res.done_today))
      .catch(() => {})
      .finally(() => setCheckingToday(false))
  }, [])

  useEffect(() => {
    checkToday()
  }, [checkToday])

  const setAnswer = (text: string) => {
    const next = [...answers]
    next[step] = text
    setAnswers(next)
  }

  const next = async () => {
    if (step < QUESTIONS.length - 1) {
      setStep(step + 1)
      return
    }
    setSaving(true)
    try {
      await api.saveMuhasaba(QUESTIONS.map((q, i) => ({ q: q.q, a: answers[i] })))
      const res = await api.muhasabaStreak()
      setStreak(res.streak)
      setDone(true)
    } catch {
      // stay on the last question — the user can retry "Завершить"
    } finally {
      setSaving(false)
    }
  }

  if (checkingToday) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.g2} />
      </View>
    )
  }

  if (alreadyDoneToday && !done) {
    return (
      <View style={styles.center}>
        <Text style={styles.doneIcon}>🌙</Text>
        <Text style={styles.doneTitle}>Сегодня уже отвечал</Text>
        <Text style={styles.doneText}>Вечерний самоотчёт на сегодня уже записан. До встречи завтра.</Text>
        <Pressable style={styles.backButton} onPress={() => navigation.goBack()}>
          <Text style={styles.backButtonText}>Назад</Text>
        </Pressable>
      </View>
    )
  }

  if (done) {
    return (
      <View style={styles.center}>
        <Text style={styles.doneIcon}>🌿</Text>
        <Text style={styles.doneTitle}>Баракаллаху фик</Text>
        <Text style={styles.doneText}>Ты завершил день честно. Вечерний самоотчёт записан.</Text>
        {streak !== null && streak > 1 && (
          <Text style={styles.streakText}>🔥 {streak} {streak === 1 ? 'день' : 'дней'} подряд</Text>
        )}
        <Pressable style={styles.backButton} onPress={() => navigation.goBack()}>
          <Text style={styles.backButtonText}>Спокойной ночи 🌙</Text>
        </Pressable>
      </View>
    )
  }

  const q = QUESTIONS[step]
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>Вечерний самоотчёт · Вопрос {step + 1} из {QUESTIONS.length}</Text>
      <Text style={styles.question}>{q.prompt}</Text>
      <Text style={styles.hint}>{q.hint}</Text>
      <TextInput
        style={styles.input}
        value={answers[step]}
        onChangeText={setAnswer}
        placeholder="Ответь честно, здесь никто не оценивает…"
        placeholderTextColor={colors.muted}
        multiline
        autoFocus
      />
      <Pressable style={styles.continueButton} onPress={next} disabled={saving || !answers[step].trim()}>
        {saving ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.continueButtonText}>
            {step < QUESTIONS.length - 1 ? 'Дальше' : 'Завершить'}
          </Text>
        )}
      </Pressable>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg, padding: 24 },
  content: { padding: 24, paddingTop: 40, flexGrow: 1 },
  eyebrow: { fontSize: 13, fontWeight: '600', color: colors.gold, marginBottom: 16, textAlign: 'center' },
  question: { fontSize: 20, fontWeight: '700', color: colors.g1, textAlign: 'center', marginBottom: 8, lineHeight: 28 },
  hint: { fontSize: 13, color: colors.sub, fontStyle: 'italic', textAlign: 'center', marginBottom: 24 },
  input: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 16,
    fontSize: 15,
    color: colors.text,
    minHeight: 120,
    textAlignVertical: 'top',
    marginBottom: 24,
    ...shadow.card,
  },
  continueButton: {
    backgroundColor: colors.g2,
    paddingVertical: 14,
    borderRadius: radius.button,
    alignItems: 'center',
  },
  continueButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  doneIcon: { fontSize: 48, marginBottom: 12 },
  doneTitle: { fontSize: 22, fontWeight: '700', color: colors.g1, marginBottom: 8, textAlign: 'center' },
  doneText: { fontSize: 14, color: colors.sub, textAlign: 'center', marginBottom: 16, lineHeight: 20 },
  streakText: { fontSize: 15, fontWeight: '700', color: colors.gold, marginBottom: 24 },
  backButton: {
    backgroundColor: colors.g2,
    paddingVertical: 12,
    paddingHorizontal: 28,
    borderRadius: radius.button,
  },
  backButtonText: { color: '#fff', fontSize: 15, fontWeight: '600' },
})
