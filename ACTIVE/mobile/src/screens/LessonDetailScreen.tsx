import { NativeStackScreenProps } from '@react-navigation/native-stack'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, Alert, Pressable, ScrollView, Share, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import { useTheme } from '../context/ThemeContext'
import { TOTAL_STEPS } from '../data/weeks'
import { LessonsStackParamList } from '../navigation/types'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { api, QuizQuestion } from '../utils/api'

type SkillLevel = 'I' | 'II' | 'III'
const SKILL_ORDER: SkillLevel[] = ['I', 'II', 'III']
const SKILL_LABELS: Record<SkillLevel, string> = { I: 'Начальный', II: 'Практика', III: 'Мастер' }

type Props = NativeStackScreenProps<LessonsStackParamList, 'LessonDetail'>

function lessonParagraphs(text: string): string[] {
  return text.split(/\n\s*\n|\n/).map((part) => part.trim()).filter(Boolean)
}

export default function LessonDetailScreen({ route, navigation }: Props) {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
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
  const [correctCount, setCorrectCount] = useState(0)
  const [finishing, setFinishing] = useState(false)
  const [autoStartDone, setAutoStartDone] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(false)
    Promise.all([api.content(level, week), api.participant()])
      .then(([lessonContent, participant]) => {
        setContent(lessonContent)
        setSkill((participant.vakt_level as SkillLevel) || 'I')
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [level, week])

  useEffect(() => { load() }, [load])

  const finishStep = useCallback(async () => {
    setFinishing(true)
    try {
      const result = await api.weekAck(level, week)
      const shareStep = () => Share.share({ message: `Я прошёл Шаг ${globalWeek} программы IQ Barakah. Альхамдулиллях.` }).catch(() => {})
      if (result.graduated) {
        Alert.alert(
          'Уровень завершён',
          'Все шаги этого уровня пройдены. Следующий сезон откроется после активации куратором в боте.',
          [
            { text: 'Поделиться', onPress: shareStep },
            { text: 'К карте пути', onPress: () => navigation.goBack() },
          ],
        )
      } else {
        Alert.alert(
          'Шаг завершён',
          `Шаг ${globalWeek} сохранён в вашем прогрессе. Продолжайте путь в своём темпе.`,
          [
            { text: 'Поделиться', onPress: shareStep },
            { text: 'К карте пути', onPress: () => navigation.goBack() },
          ],
        )
      }
    } catch {
      Alert.alert('Не удалось сохранить', 'Проверьте интернет-соединение и попробуйте снова.')
    } finally {
      setFinishing(false)
    }
  }, [globalWeek, level, navigation, week])

  const startQuiz = useCallback(async () => {
    if (!skill) return
    setQuizLoading(true)
    try {
      const quiz = await api.quiz(level, week)
      const availableQuestions = quiz[skill] ?? []
      if (availableQuestions.length === 0) {
        await finishStep()
        return
      }
      setQuestions(availableQuestions)
      setQuizIndex(0)
      setSelectedAnswer(null)
      setCorrectCount(0)
      setQuizStarted(true)
    } catch {
      Alert.alert('Не удалось загрузить тест', 'Проверьте интернет-соединение и попробуйте снова.')
    } finally {
      setQuizLoading(false)
    }
  }, [finishStep, level, skill, week])

  useEffect(() => {
    if (route.params.autoStartQuiz && !autoStartDone && !loading && !error && skill && content) {
      setAutoStartDone(true)
      void startQuiz()
    }
  }, [autoStartDone, content, error, loading, route.params.autoStartQuiz, skill, startQuiz])

  const answerQuestion = (optionIndex: number) => {
    if (selectedAnswer !== null) return
    setSelectedAnswer(optionIndex)
    if (optionIndex === questions[quizIndex]?.correct) setCorrectCount((value) => value + 1)
  }

  const nextQuestion = () => {
    if (quizIndex + 1 < questions.length) {
      setQuizIndex((value) => value + 1)
      setSelectedAnswer(null)
    } else {
      void finishStep()
    }
  }

  if (loading) return <View style={styles.center}><ActivityIndicator color={colors.gold} /></View>
  if (error || !content || !skill) return <ErrorState message="Не удалось загрузить урок" onRetry={load} />

  if (quizStarted) {
    const question = questions[quizIndex]
    const answered = selectedAnswer !== null
    const answerCorrect = selectedAnswer === question.correct
    const quizProgress = ((quizIndex + (answered ? 1 : 0)) / questions.length) * 100

    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.quizContent}>
        <View style={styles.quizHeader}>
          <View style={styles.quizHeaderTop}>
            <Pressable onPress={() => setQuizStarted(false)} hitSlop={10}><Text style={styles.closeQuiz}>‹ Урок</Text></Pressable>
            <Text style={styles.quizCounter}>{quizIndex + 1} из {questions.length}</Text>
          </View>
          <View style={styles.quizProgressTrack}><View style={[styles.quizProgressFill, { width: `${quizProgress}%` }]} /></View>
        </View>

        <Text style={styles.quizEyebrow}>ПРОВЕРКА ПОНИМАНИЯ</Text>
        <Text style={styles.quizQuestion}>{question.q}</Text>

        <View style={styles.optionsList}>
          {question.opts.map((option, index) => {
            const selected = selectedAnswer === index
            const correct = index === question.correct
            const showCorrect = answered && correct
            const showWrong = answered && selected && !correct
            return (
              <Pressable
                key={index}
                accessibilityRole="radio"
                accessibilityState={{ checked: selected, disabled: answered }}
                disabled={answered}
                style={[styles.quizOption, showCorrect && styles.quizOptionCorrect, showWrong && styles.quizOptionWrong]}
                onPress={() => answerQuestion(index)}
              >
                <View style={[styles.optionLetter, showCorrect && styles.optionLetterCorrect, showWrong && styles.optionLetterWrong]}>
                  <Text style={[styles.optionLetterText, (showCorrect || showWrong) && styles.optionLetterTextActive]}>{String.fromCharCode(65 + index)}</Text>
                </View>
                <Text style={[styles.quizOptionText, showWrong && styles.quizOptionTextWrong]}>{option}</Text>
                {showCorrect && <Text style={styles.answerMarkCorrect}>✓</Text>}
                {showWrong && <Text style={styles.answerMarkWrong}>×</Text>}
              </Pressable>
            )
          })}
        </View>

        {answered && (
          <View style={[styles.feedbackCard, answerCorrect ? styles.feedbackCorrect : styles.feedbackWrong]}>
            <Text style={[styles.feedbackTitle, !answerCorrect && styles.feedbackTitleWrong]}>{answerCorrect ? 'Верно' : 'Стоит повторить'}</Text>
            <Text style={styles.feedbackText}>
              {answerCorrect ? 'Ответ закреплён. Переходите дальше.' : `Правильный ответ: ${question.opts[question.correct]}`}
            </Text>
            <Text style={styles.scoreText}>Правильных ответов: {correctCount} из {quizIndex + 1}</Text>
          </View>
        )}

        {answered && (
          <Pressable style={styles.primaryButton} onPress={nextQuestion} disabled={finishing}>
            {finishing ? <ActivityIndicator color={colors.onPrimary} /> : (
              <Text style={styles.primaryButtonText}>{quizIndex + 1 < questions.length ? 'Следующий вопрос' : 'Завершить шаг'}</Text>
            )}
          </Pressable>
        )}
      </ScrollView>
    )
  }

  const paragraphs = lessonParagraphs(content.text[skill])
  const tasks = content.tasks[skill] ?? []
  const progressPct = Math.round((globalWeek / TOTAL_STEPS) * 100)

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.lessonHero}>
        <Text style={styles.lessonEyebrow}>ШАГ {globalWeek} ИЗ {TOTAL_STEPS}</Text>
        <Text style={styles.title}>{content.title}</Text>
        <View style={styles.heroProgressMeta}>
          <Text style={styles.heroProgressText}>Общий путь</Text>
          <Text style={styles.heroProgressValue}>{progressPct}%</Text>
        </View>
        <View style={styles.heroProgressTrack}><View style={[styles.heroProgressFill, { width: `${progressPct}%` }]} /></View>
      </View>

      <View style={styles.skillCard}>
        <Text style={styles.sectionEyebrow}>ВАШ УРОВЕНЬ</Text>
        <View style={styles.skillRow}>
          {SKILL_ORDER.map((item) => {
            const reached = SKILL_ORDER.indexOf(item) <= SKILL_ORDER.indexOf(skill)
            const current = item === skill
            return (
              <View key={item} style={styles.skillItem}>
                <View style={[styles.skillNode, reached && styles.skillNodeReached, current && styles.skillNodeCurrent]}>
                  <Text style={[styles.skillNodeText, reached && styles.skillNodeTextReached]}>{reached ? '✓' : '⌑'}</Text>
                </View>
                <Text style={[styles.skillLabel, current && styles.skillLabelCurrent]}>{SKILL_LABELS[item]}</Text>
              </View>
            )
          })}
        </View>
        <Text style={styles.skillHint}>Уровень назначается по диагностике и открывается куратором по мере роста.</Text>
      </View>

      {!!content.hadith && (
        <View style={styles.reminderCard}>
          <Text style={styles.reminderIcon}>☾</Text>
          <View style={styles.reminderContent}>
            <Text style={styles.sectionEyebrow}>НАПОМИНАНИЕ УРОКА</Text>
            <Text style={styles.hadith}>{content.hadith}</Text>
          </View>
        </View>
      )}

      <View style={styles.readingCard}>
        <Text style={styles.sectionEyebrow}>МАТЕРИАЛ УРОКА</Text>
        {paragraphs.map((paragraph, index) => <Text key={index} style={styles.lessonText}>{paragraph}</Text>)}
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Практика</Text>
        <Text style={styles.sectionCount}>{tasks.length} заданий</Text>
      </View>
      <View style={styles.tasksCard}>
        {tasks.map((task, index) => (
          <View key={index} style={[styles.taskRow, index < tasks.length - 1 && styles.taskRowBorder]}>
            <View style={styles.taskNumber}><Text style={styles.taskNumberText}>{index + 1}</Text></View>
            <Text style={styles.taskText}>{task}</Text>
          </View>
        ))}
      </View>

      <View style={styles.finishCard}>
        <Text style={styles.finishEyebrow}>ГОТОВЫ ЗАКРЕПИТЬ УРОК?</Text>
        <Text style={styles.finishTitle}>Короткая проверка понимания</Text>
        <Text style={styles.finishSub}>Ответьте на вопросы, после чего шаг сохранится в общем прогрессе.</Text>
        <Pressable style={styles.primaryButton} onPress={() => void startQuiz()} disabled={quizLoading}>
          {quizLoading ? <ActivityIndicator color={colors.onPrimary} /> : <Text style={styles.primaryButtonText}>Начать тест</Text>}
        </Pressable>
      </View>
    </ScrollView>
  )
}

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
    content: { padding: 16, paddingBottom: 44 },
    lessonHero: { padding: 20, borderRadius: 22, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadow.card },
    lessonEyebrow: { color: colors.gold, fontSize: 10, fontWeight: '900', letterSpacing: 1 },
    title: { color: colors.text, fontSize: 26, fontWeight: '800', lineHeight: 32, marginTop: 12 },
    heroProgressMeta: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 22, marginBottom: 8 },
    heroProgressText: { color: colors.muted, fontSize: 11 },
    heroProgressValue: { color: colors.gold, fontSize: 11, fontWeight: '900' },
    heroProgressTrack: { height: 5, borderRadius: 3, overflow: 'hidden', backgroundColor: colors.gsoft },
    heroProgressFill: { height: '100%', borderRadius: 3, backgroundColor: colors.gold },
    sectionEyebrow: { color: colors.gold, fontSize: 10, fontWeight: '900', letterSpacing: 0.9 },
    skillCard: { marginTop: 14, padding: 16, borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
    skillRow: { flexDirection: 'row', marginTop: 14 },
    skillItem: { flex: 1, alignItems: 'center' },
    skillNode: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: colors.incomplete, backgroundColor: colors.cardRaised },
    skillNodeReached: { borderColor: colors.completed, backgroundColor: colors.successSoft },
    skillNodeCurrent: { borderColor: colors.gold, borderWidth: 2, shadowColor: colors.gold, shadowOpacity: 0.22, shadowRadius: 8, elevation: 2 },
    skillNodeText: { color: colors.incomplete, fontSize: 12, fontWeight: '900' },
    skillNodeTextReached: { color: colors.completed },
    skillLabel: { color: colors.muted, fontSize: 10, fontWeight: '700', marginTop: 7 },
    skillLabelCurrent: { color: colors.gold },
    skillHint: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 14 },
    reminderCard: { flexDirection: 'row', gap: 13, marginTop: 14, padding: 17, borderRadius: radius.card, backgroundColor: colors.overlay, borderWidth: 1, borderColor: colors.border },
    reminderIcon: { color: colors.gold, fontSize: 26 },
    reminderContent: { flex: 1 },
    hadith: { color: colors.text, fontSize: 14, fontStyle: 'italic', lineHeight: 21, marginTop: 7 },
    readingCard: { marginTop: 14, padding: 20, borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadow.card },
    lessonText: { color: colors.text, fontSize: 16, lineHeight: 25, marginTop: 14 },
    sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 24, marginBottom: 10 },
    sectionTitle: { color: colors.text, fontSize: 19, fontWeight: '800' },
    sectionCount: { color: colors.gold, fontSize: 11, fontWeight: '800' },
    tasksCard: { paddingHorizontal: 15, borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadow.card },
    taskRow: { minHeight: 70, flexDirection: 'row', alignItems: 'center', paddingVertical: 12 },
    taskRowBorder: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    taskNumber: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.overlay, borderWidth: 1, borderColor: colors.gold },
    taskNumberText: { color: colors.gold, fontSize: 12, fontWeight: '900' },
    taskText: { flex: 1, color: colors.text, fontSize: 13, lineHeight: 19, marginLeft: 12 },
    finishCard: { marginTop: 24, padding: 20, borderRadius: 22, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.gold, ...shadow.card },
    finishEyebrow: { color: colors.gold, fontSize: 10, fontWeight: '900', letterSpacing: 0.9 },
    finishTitle: { color: colors.text, fontSize: 20, fontWeight: '800', marginTop: 8 },
    finishSub: { color: colors.sub, fontSize: 12, lineHeight: 18, marginTop: 5 },
    primaryButton: { minHeight: 52, alignItems: 'center', justifyContent: 'center', borderRadius: radius.button, backgroundColor: colors.g2, borderWidth: 1, borderColor: colors.gold, marginTop: 18 },
    primaryButtonText: { color: colors.onPrimary, fontSize: 15, fontWeight: '800' },
    quizContent: { padding: 18, paddingBottom: 44 },
    quizHeader: { marginBottom: 30 },
    quizHeaderTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 11 },
    closeQuiz: { color: colors.gold, fontSize: 13, fontWeight: '800' },
    quizCounter: { color: colors.muted, fontSize: 12, fontWeight: '700' },
    quizProgressTrack: { height: 6, borderRadius: 3, overflow: 'hidden', backgroundColor: colors.gsoft },
    quizProgressFill: { height: '100%', borderRadius: 3, backgroundColor: colors.gold },
    quizEyebrow: { color: colors.gold, fontSize: 10, fontWeight: '900', letterSpacing: 1 },
    quizQuestion: { color: colors.text, fontSize: 24, fontWeight: '800', lineHeight: 31, marginTop: 12 },
    optionsList: { gap: 10, marginTop: 24 },
    quizOption: { minHeight: 66, flexDirection: 'row', alignItems: 'center', padding: 13, borderRadius: radius.button, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadow.card },
    quizOptionCorrect: { borderColor: colors.completed, backgroundColor: colors.successSoft },
    quizOptionWrong: { borderColor: colors.danger, backgroundColor: colors.dangerSoft },
    optionLetter: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.overlay },
    optionLetterCorrect: { backgroundColor: colors.completed },
    optionLetterWrong: { backgroundColor: colors.danger },
    optionLetterText: { color: colors.gold, fontSize: 12, fontWeight: '900' },
    optionLetterTextActive: { color: colors.onPrimary },
    quizOptionText: { flex: 1, color: colors.text, fontSize: 14, lineHeight: 20, marginLeft: 12 },
    quizOptionTextWrong: { color: colors.danger },
    answerMarkCorrect: { color: colors.completed, fontSize: 19, fontWeight: '900' },
    answerMarkWrong: { color: colors.danger, fontSize: 21, fontWeight: '900' },
    feedbackCard: { marginTop: 18, padding: 16, borderRadius: radius.button, borderWidth: 1 },
    feedbackCorrect: { backgroundColor: colors.successSoft, borderColor: colors.completed },
    feedbackWrong: { backgroundColor: colors.dangerSoft, borderColor: colors.danger },
    feedbackTitle: { color: colors.completed, fontSize: 16, fontWeight: '900' },
    feedbackTitleWrong: { color: colors.danger },
    feedbackText: { color: colors.text, fontSize: 13, lineHeight: 19, marginTop: 5 },
    scoreText: { color: colors.muted, fontSize: 11, marginTop: 9 },
  })
}
