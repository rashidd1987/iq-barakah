import React, { useCallback, useState } from 'react'
import { useFocusEffect, useNavigation } from '@react-navigation/native'
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import ScreenHeader from '../components/ScreenHeader'
import { DAILY, NAMAZ, ONETIME, WEEKLY } from '../data/habits'
import { globalWeekIndex } from '../data/weeks'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'

type Habits = {
  namaz: Record<string, boolean>
  daily: Record<string, boolean>
  weekly: Record<string, boolean>
  onetime: Record<string, boolean>
  tasks: Record<string, boolean>
}

const EMPTY_HABITS: Habits = { namaz: {}, daily: {}, weekly: {}, onetime: {}, tasks: {} }

const WEEKDAY_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

function toDateKey(d: Date): string {
  return d.toISOString().slice(0, 10)
}

// Monday-start week containing `today` — matches the miniapp's tracker week strip.
function currentWeekDates(): Date[] {
  const today = new Date()
  const dayOfWeek = (today.getDay() + 6) % 7 // 0 = Monday
  const monday = new Date(today)
  monday.setDate(today.getDate() - dayOfWeek)
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    return d
  })
}

export default function TrackerScreen() {
  const navigation = useNavigation<any>()
  const weekDates = currentWeekDates()
  const todayKey = toDateKey(new Date())
  const [selectedDate, setSelectedDate] = useState(todayKey)
  const [habits, setHabits] = useState<Habits>(EMPTY_HABITS)
  const [stepTasks, setStepTasks] = useState<string[]>([])
  const [step, setStep] = useState<{ level: string; week: number; globalWeek: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async (date: string) => {
    setLoading(true)
    setError(false)
    try {
      const [records, participant] = await Promise.all([api.tracker(30), api.participant()])
      const record = records.find((r) => r.date === date) as { habits?: Partial<Habits> } | undefined
      setHabits({ ...EMPTY_HABITS, ...(record?.habits ?? {}) })

      const skill = (participant.vakt_level as 'I' | 'II' | 'III') || 'I'
      const content = await api.content(participant.level, participant.week)
      setStepTasks(content.tasks[skill] ?? [])
      setStep({
        level: participant.level,
        week: participant.week,
        globalWeek: globalWeekIndex(participant.level, participant.week),
      })
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useFocusEffect(
    useCallback(() => {
      load(selectedDate)
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [load, selectedDate]),
  )

  const selectDate = (date: string) => {
    setSelectedDate(date)
    load(date)
  }

  const toggle = async (bucket: keyof Habits, id: string) => {
    const previous = habits
    const next: Habits = { ...habits, [bucket]: { ...habits[bucket], [id]: !habits[bucket][id] } }
    setHabits(next)
    setSaving(true)
    try {
      await api.saveTracker(selectedDate, next)
    } catch {
      setHabits(previous) // save failed — revert the optimistic tap instead of showing unsaved state as done
      Alert.alert('Не сохранилось', 'Проверьте интернет-соединение и попробуйте ещё раз.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.g2} />
      </View>
    )
  }

  if (error) {
    return <ErrorState message="Не удалось загрузить трекер" onRetry={() => load(selectedDate)} />
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <ScreenHeader badge="Трекер" title="Сегодня" subtitle="Отмечайте выполненное" />
      <View style={styles.body}>
      <View style={styles.weekStrip}>
        {weekDates.map((d) => {
          const key = toDateKey(d)
          const isSelected = key === selectedDate
          const isToday = key === todayKey
          return (
            <Pressable
              key={key}
              style={[styles.dayCell, isSelected && styles.dayCellSelected]}
              onPress={() => selectDate(key)}
            >
              <Text style={[styles.dayLabel, isSelected && styles.dayLabelSelected]}>
                {WEEKDAY_LABELS[(d.getDay() + 6) % 7]}
              </Text>
              <Text style={[styles.dayNum, isSelected && styles.dayNumSelected]}>{d.getDate()}</Text>
              {isToday && <View style={styles.todayDot} />}
            </Pressable>
          )
        })}
      </View>

      {stepTasks.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📋 Задания шага</Text>
          {stepTasks.map((task, i) => {
            const id = String(i)
            const done = !!habits.tasks[id]
            return (
              <Pressable
                key={id}
                style={[styles.card, done && styles.cardDone]}
                onPress={() => toggle('tasks', id)}
              >
                <View style={styles.itemInfo}>
                  <Text style={styles.taskText}>{task}</Text>
                </View>
                <View style={[styles.check, done && styles.checkDone]}>
                  {done && <Text style={styles.checkMark}>✓</Text>}
                </View>
              </Pressable>
            )
          })}

          {stepTasks.every((_, i) => !!habits.tasks[String(i)]) && (
            <View style={styles.celebrationCard}>
              <View style={styles.celebrationRow}>
                <Text style={styles.celebrationIcon}>🎉</Text>
                <View style={styles.celebrationText}>
                  <Text style={styles.celebrationTitle}>Все задания выполнены! Альхамдулиллях</Text>
                  <Text style={styles.celebrationSub}>Ты молодец — продолжай в том же духе 💚</Text>
                </View>
              </View>
              {step && (
                <Pressable
                  style={styles.testButton}
                  onPress={() =>
                    navigation.navigate('Lessons', {
                      screen: 'LessonDetail',
                      params: { level: step.level, week: step.week, globalWeek: step.globalWeek, autoStartQuiz: true },
                    })
                  }
                >
                  <Text style={styles.testButtonText}>🎯 Пройти тест шага</Text>
                </Pressable>
              )}
            </View>
          )}
        </View>
      )}

      <Section title="🕌 Намаз" bucket="namaz" items={NAMAZ} habits={habits} onToggle={toggle} />
      <Section title="☀️ Каждый день" bucket="daily" items={DAILY} habits={habits} onToggle={toggle} />
      <Section title="📅 На неделю" bucket="weekly" items={WEEKLY} habits={habits} onToggle={toggle} />
      <Section title="🔖 Один раз" bucket="onetime" items={ONETIME} habits={habits} onToggle={toggle} />
      {saving && <Text style={styles.savingHint}>Сохранение…</Text>}
      </View>
    </ScrollView>
  )
}

function Section({
  title,
  bucket,
  items,
  habits,
  onToggle,
}: {
  title: string
  bucket: keyof Habits
  items: { id: string; label: string; icon: string; sub?: string }[]
  habits: Habits
  onToggle: (bucket: keyof Habits, id: string) => void
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {items.map((item) => {
        const done = !!habits[bucket][item.id]
        return (
          <Pressable key={item.id} style={[styles.card, done && styles.cardDone]} onPress={() => onToggle(bucket, item.id)}>
            <Text style={styles.itemIcon}>{item.icon}</Text>
            <View style={styles.itemInfo}>
              <Text style={styles.itemLabel}>{item.label}</Text>
              {!!item.sub && <Text style={styles.itemSub}>{item.sub}</Text>}
            </View>
            <View style={[styles.check, done && styles.checkDone]}>{done && <Text style={styles.checkMark}>✓</Text>}</View>
          </Pressable>
        )
      })}
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  content: { paddingBottom: 32 },
  body: { padding: 16, marginTop: -16 },
  weekStrip: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 10,
    marginBottom: 20,
    ...shadow.card,
  },
  dayCell: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 10 },
  dayCellSelected: { backgroundColor: colors.g2 },
  dayLabel: { fontSize: 11, color: colors.muted, marginBottom: 2 },
  dayLabelSelected: { color: colors.goldpale },
  dayNum: { fontSize: 15, fontWeight: '700', color: colors.text },
  dayNumSelected: { color: '#fff' },
  todayDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: colors.gold, marginTop: 3 },
  section: { marginBottom: 20 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: 8 },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    ...shadow.card,
  },
  cardDone: { backgroundColor: colors.gpale },
  itemIcon: { fontSize: 22, marginRight: 12 },
  itemInfo: { flex: 1 },
  itemLabel: { fontSize: 14, fontWeight: '600', color: colors.text },
  itemSub: { fontSize: 12, color: colors.sub, marginTop: 2 },
  taskText: { fontSize: 13, color: colors.text, lineHeight: 19 },
  check: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 8,
  },
  checkDone: { backgroundColor: colors.g2, borderColor: colors.g2 },
  checkMark: { color: '#fff', fontSize: 13, fontWeight: '700' },
  savingHint: { textAlign: 'center', color: colors.muted, fontSize: 12 },
  celebrationCard: {
    backgroundColor: colors.g2,
    borderRadius: radius.card,
    padding: 16,
    marginTop: 4,
  },
  celebrationRow: { flexDirection: 'row', alignItems: 'center' },
  celebrationIcon: { fontSize: 26, marginRight: 12 },
  celebrationText: { flex: 1 },
  celebrationTitle: { fontSize: 13, fontWeight: '700', color: '#fff' },
  celebrationSub: { fontSize: 12, color: 'rgba(255,255,255,0.75)', marginTop: 2 },
  testButton: {
    backgroundColor: colors.gold,
    borderRadius: radius.button,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 14,
  },
  testButtonText: { color: '#fff', fontSize: 14, fontWeight: '700' },
})
