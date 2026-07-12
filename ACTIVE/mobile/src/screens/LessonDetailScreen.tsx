import { NativeStackScreenProps } from '@react-navigation/native-stack'
import React, { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import { LessonsStackParamList } from '../navigation/types'
import { colors, radius, shadow } from '../theme/colors'
import { api, QuizQuestion } from '../utils/api'

type SkillLevel = 'I' | 'II' | 'III'
const SKILL_ORDER: SkillLevel[] = ['I', 'II', 'III']
const SKILL_LABELS: Record<SkillLevel, string> = { I: 'Начальный', II: 'Практика', III: 'Мастер' }

type Props = NativeStackScreenProps<LessonsStackParamList, 'LessonDetail'>

export default function LessonDetailScreen({ route, navigation }: Props) {
  const { level, week, globalWeek } = route.params
  const [skill, setSkill] = useState<SkillLevel | null>(null)
  const [content, setContent] = useState<Awaited<ReturnType<typeof api.content>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const [quizStarted, setQuizStarted] = useState(false)
  const [quizLoading, setQuizLoading] = useState(false)
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [quizIndex, setQuizIndex] = useState(0)
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null)
  const [finishing, setFinishing] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(false)
    Promise.all([api.content(level, week), api.participant()])
      .then(([lessonContent, participant]) => {
        setContent(lessonContent)
        // vakt_level holds the student's assigned skill tier (I/II/III) — it's earned
        // through the diagnostic test, not something the student picks for themselves.
        setSkill((participant.vakt_level as SkillLevel) || 'I')
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [level, week])

  useEffect(() => {
    load()
  }, [load])

  const [autoStartDone, setAutoStartDone] = useState(false)
  useEffect(() => {
    // Coming from the Tracker's "all tasks done" celebration — skip straight to the
    // quiz instead of making the student find the button again on the lesson page.
    if (route.params.autoStartQuiz && !autoStartDone && !loading && !error && skill && content) {
      setAutoStartDone(true)
      startQuiz()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route.params.autoStartQuiz, autoStartDone, loading, error, skill, content])

  const finishStep = useCallback(async () => {
    setFinishing(true)
    try {
      const result = await api.weekAck(level, week)
      if (result.graduated) {
        Alert.alert(
          '🏆 Уровень завершён!',
          'Ты прошёл все шаги этого уровня. Следующий сезон откроется, когда куратор активирует его в боте.',
          [{ text: 'Ок', onPress: () => navigation.goBack() }],
        )
      } else {
        Alert.alert(
          '🎉 Хвала Аллаху, ты молодец!',
          `Шаг ${globalWeek} закрыт. Так держать — каждый пройденный шаг закрепляет то, что раньше держалось только на силе воли.`,
          [{ text: 'Дальше', onPress: () => navigation.goBack() }],
        )
      }
    } catch {
      Alert.alert('Не удалось сохранить', 'Проверьте интернет-соединение и попробуйте снова.')
    } finally {
      setFinishing(false)
    }
  }, [level, week, navigation])

  const startQuiz = async () => {
    if (!skill) return
    setQuizLoading(true)
    try {
      const quiz = await api.quiz(level, week)
      const qs = quiz[skill] ?? []
      if (qs.length === 0) {
        // No quiz content for this step — fall back to direct completion rather than blocking progress.
        await finishStep()
        return
      }
      setQuestions(qs)
      setQuizIndex(0)
      setSelectedAnswer(null)
      setQuizStarted(true)
    } catch {
      Alert.alert('Не удалось загрузить тест', 'Проверьте интернет-соединение и попробуйте снова.')
    } finally {
      setQuizLoading(false)
    }
  }

  const answerQuestion = (optionIndex: number) => {
    if (selectedAnswer !== null) return // already answered — feedback is shown, wait for "Далее"
    setSelectedAnswer(optionIndex)
  }

  const nextQuestion = () => {
    if (quizIndex + 1 < questions.length) {
      setQuizIndex(quizIndex + 1)
      setSelectedAnswer(null)
    } else {
      finishStep()
    }
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.g2} />
      </View>
    )
  }

  if (error || !content || !skill) {
    return <ErrorState message="Не удалось загрузить урок" onRetry={load} />
  }

  if (quizStarted) {
    const q = questions[quizIndex]
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.stepLabel}>Вопрос {quizIndex + 1} из {questions.length}</Text>
        <Text style={styles.quizQuestion}>{q.q}</Text>

        {q.opts.map((opt, i) => {
          const isSelected = selectedAnswer === i
          const isCorrect = i === q.correct
          const showFeedback = selectedAnswer !== null
          let optionStyle = styles.quizOption
          if (showFeedback && isCorrect) optionStyle = { ...styles.quizOption, ...styles.quizOptionCorrect }
          else if (showFeedback && isSelected && !isCorrect) optionStyle = { ...styles.quizOption, ...styles.quizOptionWrong }
          return (
            <Pressable key={i} style={optionStyle} onPress={() => answerQuestion(i)} disabled={showFeedback}>
              <Text style={styles.quizOptionText}>
                {String.fromCharCode(65 + i)}) {opt}
              </Text>
            </Pressable>
          )
        })}

        {selectedAnswer !== null && (
          <>
            <Text style={styles.quizFeedback}>
              {selectedAnswer === q.correct ? '✅ Верно!' : `🔄 Не совсем. Правильный ответ: ${q.opts[q.correct]}`}
            </Text>
            <Pressable style={styles.completeButton} onPress={nextQuestion} disabled={finishing}>
              {finishing ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.completeButtonText}>
                  {quizIndex + 1 < questions.length ? 'Следующий вопрос' : 'Завершить шаг'}
                </Text>
              )}
            </Pressable>
          </>
        )}
      </ScrollView>
    )
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.stepLabel}>Шаг {globalWeek} из 30</Text>
      <Text style={styles.title}>{content.title}</Text>
      {!!content.hadith && <Text style={styles.hadith}>{content.hadith}</Text>}

      <View style={styles.growthRow}>
        {SKILL_ORDER.map((s) => {
          const reached = SKILL_ORDER.indexOf(s) <= SKILL_ORDER.indexOf(skill)
          const isCurrent = s === skill
          return (
            <View key={s} style={[styles.growthStep, isCurrent && styles.growthStepCurrent]}>
              <Text style={[styles.growthStepText, isCurrent && styles.growthStepTextCurrent]}>
                {reached ? '' : '🔒 '}
                {SKILL_LABELS[s]}
              </Text>
            </View>
          )
        })}
      </View>
      <Text style={styles.growthHint}>
        Твой текущий уровень — «{SKILL_LABELS[skill]}». Следующие уровни открываются куратором по мере роста.
      </Text>

      <View style={[styles.card, styles.textCard]}>
        <Text style={styles.lessonText}>{content.text[skill]}</Text>
      </View>

      <Text style={styles.sectionTitle}>Задания</Text>
      {content.tasks[skill]?.map((task, i) => (
        <View key={i} style={[styles.card, styles.taskCard]}>
          <Text style={styles.taskText}>{task}</Text>
        </View>
      ))}

      <Pressable style={styles.completeButton} onPress={startQuiz} disabled={quizLoading}>
        {quizLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.completeButtonText}>Пройти тест и завершить шаг</Text>}
      </Pressable>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40 },
  stepLabel: { fontSize: 13, fontWeight: '600', color: colors.muted, marginBottom: 4 },
  title: { fontSize: 22, fontWeight: '700', color: colors.g1, marginBottom: 8 },
  hadith: { fontSize: 14, fontStyle: 'italic', color: colors.sub, marginBottom: 16 },
  growthRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  growthStep: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: radius.button,
    backgroundColor: colors.gpale,
    alignItems: 'center',
  },
  growthStepCurrent: { backgroundColor: colors.g2 },
  growthStepText: { fontSize: 12, fontWeight: '600', color: colors.g2 },
  growthStepTextCurrent: { color: '#fff' },
  growthHint: { fontSize: 12, color: colors.muted, marginBottom: 16 },
  card: { backgroundColor: colors.card, borderRadius: radius.card, ...shadow.card },
  textCard: { padding: 16, marginBottom: 20 },
  lessonText: { fontSize: 15, lineHeight: 22, color: colors.text },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 8 },
  taskCard: { padding: 12, marginBottom: 8 },
  taskText: { fontSize: 14, color: colors.text },
  quizQuestion: { fontSize: 18, fontWeight: '700', color: colors.g1, marginBottom: 20, lineHeight: 25 },
  quizOption: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 14,
    marginBottom: 10,
    borderWidth: 2,
    borderColor: 'transparent',
    ...shadow.card,
  },
  quizOptionCorrect: { borderColor: colors.g2, backgroundColor: colors.gpale },
  quizOptionWrong: { borderColor: '#c0392b', backgroundColor: '#fdecea' },
  quizOptionText: { fontSize: 14, color: colors.text, lineHeight: 20 },
  quizFeedback: { fontSize: 14, fontWeight: '600', color: colors.text, marginTop: 8, marginBottom: 16, textAlign: 'center' },
  completeButton: {
    marginTop: 16,
    backgroundColor: colors.g2,
    paddingVertical: 14,
    borderRadius: radius.button,
    alignItems: 'center',
  },
  completeButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
})
