import { NativeStackScreenProps } from '@react-navigation/native-stack'
import React, { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import { LessonsStackParamList } from '../navigation/types'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'

type SkillLevel = 'I' | 'II' | 'III'
const SKILL_LABELS: Record<SkillLevel, string> = { I: 'Начальный', II: 'Практика', III: 'Мастер' }

type Props = NativeStackScreenProps<LessonsStackParamList, 'LessonDetail'>

export default function LessonDetailScreen({ route, navigation }: Props) {
  const { level, week } = route.params
  const [skill, setSkill] = useState<SkillLevel>('I')
  const [content, setContent] = useState<Awaited<ReturnType<typeof api.content>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [acking, setAcking] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(false)
    api
      .content(level, week)
      .then(setContent)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [level, week])

  useEffect(() => {
    load()
  }, [load])

  const handleComplete = async () => {
    setAcking(true)
    try {
      await api.weekAck(level, week)
      navigation.goBack()
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

  if (error || !content) {
    return <ErrorState message="Не удалось загрузить урок" onRetry={load} />
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{content.title}</Text>
      {!!content.hadith && <Text style={styles.hadith}>{content.hadith}</Text>}

      <View style={styles.skillRow}>
        {(['I', 'II', 'III'] as SkillLevel[]).map((s) => (
          <Pressable
            key={s}
            style={[styles.skillTab, skill === s && styles.skillTabActive]}
            onPress={() => setSkill(s)}
          >
            <Text style={[styles.skillTabText, skill === s && styles.skillTabTextActive]}>
              {SKILL_LABELS[s]}
            </Text>
          </Pressable>
        ))}
      </View>

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
  title: { fontSize: 22, fontWeight: '700', color: colors.g1, marginBottom: 8 },
  hadith: { fontSize: 14, fontStyle: 'italic', color: colors.sub, marginBottom: 16 },
  skillRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  skillTab: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: radius.button,
    backgroundColor: colors.gpale,
    alignItems: 'center',
  },
  skillTabActive: { backgroundColor: colors.g2 },
  skillTabText: { fontSize: 13, fontWeight: '600', color: colors.g2 },
  skillTabTextActive: { color: '#fff' },
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
