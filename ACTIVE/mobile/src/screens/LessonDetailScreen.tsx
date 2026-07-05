import { NativeStackScreenProps } from '@react-navigation/native-stack'
import React, { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import { LessonsStackParamList } from '../navigation/types'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'

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
  const [acking, setAcking] = useState(false)

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

  const handleComplete = async () => {
    setAcking(true)
    try {
      const result = await api.weekAck(level, week)
      if (result.graduated) {
        Alert.alert(
          '🏆 Уровень завершён!',
          'Ты прошёл все шаги этого уровня. Следующий сезон откроется, когда куратор активирует его в боте.',
          [{ text: 'Ок', onPress: () => navigation.goBack() }],
        )
      } else {
        navigation.goBack()
      }
    } catch {
      Alert.alert('Не удалось сохранить', 'Проверьте интернет-соединение и попробуйте снова.')
    } finally {
      setAcking(false)
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

      <Pressable style={styles.completeButton} onPress={handleComplete} disabled={acking}>
        {acking ? <ActivityIndicator color="#fff" /> : <Text style={styles.completeButtonText}>Урок пройден</Text>}
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
  completeButton: {
    marginTop: 16,
    backgroundColor: colors.g2,
    paddingVertical: 14,
    borderRadius: radius.button,
    alignItems: 'center',
  },
  completeButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
})
