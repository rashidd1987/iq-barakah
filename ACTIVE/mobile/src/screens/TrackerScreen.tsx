import { useFocusEffect, useNavigation } from '@react-navigation/native'
import React, { useCallback, useMemo, useState } from 'react'
import { ActivityIndicator, Alert, Pressable, ScrollView, Share, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import ScreenHeader from '../components/ScreenHeader'
import { useTheme } from '../context/ThemeContext'
import { DAILY, HabitDef, NAMAZ, ONETIME, WEEKLY } from '../data/habits'
import { globalWeekIndex } from '../data/weeks'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
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

function toDateKey(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function currentWeekDates(): Date[] {
  const today = new Date()
  const dayOfWeek = (today.getDay() + 6) % 7
  const monday = new Date(today)
  monday.setHours(12, 0, 0, 0)
  monday.setDate(today.getDate() - dayOfWeek)
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(monday)
    date.setDate(monday.getDate() + index)
    return date
  })
}

function countDone(bucket: Record<string, boolean>, ids: string[]): number {
  return ids.filter((id) => !!bucket[id]).length
}

export default function TrackerScreen() {
  const navigation = useNavigation<any>()
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const weekDates = useMemo(currentWeekDates, [])
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
      const record = records.find((item) => item.date === date) as { habits?: Partial<Habits> } | undefined
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
    }, [load, selectedDate]),
  )

  const toggle = async (bucket: keyof Habits, id: string) => {
    const previous = habits
    const next: Habits = { ...habits, [bucket]: { ...habits[bucket], [id]: !habits[bucket][id] } }
    setHabits(next)
    setSaving(true)
    try {
      await api.saveTracker(selectedDate, next)
    } catch {
      setHabits(previous)
      Alert.alert('Не сохранилось', 'Проверьте интернет-соединение и попробуйте ещё раз.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <View style={styles.center}><ActivityIndicator color={colors.gold} /></View>
  }
  if (error) return <ErrorState message="Не удалось загрузить трекер" onRetry={() => load(selectedDate)} />

  const taskIds = stepTasks.map((_, index) => String(index))
  const todayDone = countDone(habits.namaz, NAMAZ.map((item) => item.id))
    + countDone(habits.daily, DAILY.map((item) => item.id))
    + countDone(habits.tasks, taskIds)
  const todayTotal = NAMAZ.length + DAILY.length + stepTasks.length
  const progressPct = todayTotal > 0 ? Math.round((todayDone / todayTotal) * 100) : 0
  const allTasksDone = stepTasks.length > 0 && taskIds.every((id) => !!habits.tasks[id])
  const selectedIsToday = selectedDate === todayKey

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <ScreenHeader
        badge="Трекер"
        title={selectedIsToday ? 'Сегодня' : 'История дня'}
        subtitle="Небольшие действия складываются в путь"
      />
      <View style={styles.body}>
        <View style={styles.weekCard}>
          {weekDates.map((date) => {
            const key = toDateKey(date)
            const selected = key === selectedDate
            const today = key === todayKey
            return (
              <Pressable
                key={key}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                style={[styles.dayCell, selected && styles.dayCellSelected]}
                onPress={() => setSelectedDate(key)}
              >
                <Text style={[styles.dayLabel, selected && styles.dayTextSelected]}>{WEEKDAY_LABELS[(date.getDay() + 6) % 7]}</Text>
                <Text style={[styles.dayNumber, selected && styles.dayTextSelected]}>{date.getDate()}</Text>
                <View style={[styles.dayDot, today && styles.dayDotToday, selected && styles.dayDotSelected]} />
              </Pressable>
            )
          })}
        </View>

        <View style={styles.summaryCard}>
          <View style={styles.summaryTop}>
            <View>
              <Text style={styles.summaryEyebrow}>{selectedIsToday ? 'ПРОГРЕСС ДНЯ' : selectedDate}</Text>
              <Text style={styles.summaryTitle}>{todayDone} из {todayTotal} выполнено</Text>
            </View>
            <View style={styles.percentCircle}><Text style={styles.percentText}>{progressPct}%</Text></View>
          </View>
          <View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${progressPct}%` }]} /></View>
          <Text style={styles.summaryHint}>{progressPct === 100 ? 'День завершён. Альхамдулиллях.' : 'Продолжайте в своём темпе — без давления.'}</Text>
        </View>

        {stepTasks.length > 0 && (
          <TrackerSection
            title={`Задания шага ${step?.globalWeek ?? ''}`}
            icon="◇"
            bucket="tasks"
            items={stepTasks.map((label, index) => ({ id: String(index), label, icon: '·' }))}
            habits={habits}
            onToggle={toggle}
          />
        )}

        {allTasksDone && (
          <View style={styles.celebrationCard}>
            <Text style={styles.celebrationEyebrow}>ШАГ ГОТОВ К ЗАВЕРШЕНИЮ</Text>
            <Text style={styles.celebrationTitle}>Все задания выполнены</Text>
            <Text style={styles.celebrationSub}>Закрепите понимание коротким тестом.</Text>
            {step && (
              <Pressable
                style={styles.primaryButton}
                onPress={() => navigation.navigate('Lessons', { screen: 'LessonDetail', params: { ...step, autoStartQuiz: true } })}
              >
                <Text style={styles.primaryButtonText}>Пройти тест шага</Text>
              </Pressable>
            )}
            <Pressable
              style={styles.shareButton}
              onPress={() => Share.share({ message: 'Я выполнил все задания дня в программе IQ Barakah. Альхамдулиллях.' }).catch(() => {})}
            >
              <Text style={styles.shareButtonText}>Поделиться результатом</Text>
            </Pressable>
          </View>
        )}

        <TrackerSection title="Намаз" icon="◐" bucket="namaz" items={NAMAZ} habits={habits} onToggle={toggle} />
        <TrackerSection title="Каждый день" icon="☀︎" bucket="daily" items={DAILY} habits={habits} onToggle={toggle} />
        <TrackerSection title="На неделю" icon="□" bucket="weekly" items={WEEKLY} habits={habits} onToggle={toggle} />
        <TrackerSection title="Один раз" icon="◇" bucket="onetime" items={ONETIME} habits={habits} onToggle={toggle} />
        {saving && <Text style={styles.savingHint}>Сохранение…</Text>}
      </View>
    </ScrollView>
  )
}

function TrackerSection({ title, icon, bucket, items, habits, onToggle }: {
  title: string
  icon: string
  bucket: keyof Habits
  items: HabitDef[]
  habits: Habits
  onToggle: (bucket: keyof Habits, id: string) => void
}) {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const completed = items.filter((item) => !!habits[bucket][item.id]).length

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <View style={styles.sectionTitleRow}>
          <Text style={styles.sectionIcon}>{icon}</Text>
          <Text style={styles.sectionTitle}>{title}</Text>
        </View>
        <Text style={styles.sectionCount}>{completed}/{items.length}</Text>
      </View>
      <View style={styles.groupCard}>
        {items.map((item, index) => {
          const done = !!habits[bucket][item.id]
          return (
            <Pressable
              key={item.id}
              accessibilityRole="checkbox"
              accessibilityState={{ checked: done }}
              style={[styles.habitRow, index < items.length - 1 && styles.habitRowBorder]}
              onPress={() => onToggle(bucket, item.id)}
            >
              <View style={[styles.habitIconBox, done && styles.habitIconBoxDone]}><Text style={styles.habitIcon}>{item.icon}</Text></View>
              <View style={styles.habitInfo}>
                <Text style={[styles.habitLabel, done && styles.habitLabelDone]}>{item.label}</Text>
                {!!item.sub && <Text style={styles.habitSub}>{item.sub}</Text>}
              </View>
              <View style={[styles.check, done && styles.checkDone]}>{done && <Text style={styles.checkMark}>✓</Text>}</View>
            </Pressable>
          )
        })}
      </View>
    </View>
  )
}

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
    content: { paddingBottom: 36 },
    body: { paddingHorizontal: 16, paddingTop: 16 },
    weekCard: { flexDirection: 'row', gap: 4, padding: 6, borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadow.card },
    dayCell: { flex: 1, minHeight: 66, alignItems: 'center', justifyContent: 'center', borderRadius: 12 },
    dayCellSelected: { backgroundColor: colors.g2 },
    dayLabel: { color: colors.muted, fontSize: 10, fontWeight: '600' },
    dayNumber: { color: colors.text, fontSize: 15, fontWeight: '800', marginTop: 4 },
    dayTextSelected: { color: colors.onPrimary },
    dayDot: { width: 4, height: 4, borderRadius: 2, marginTop: 5, backgroundColor: 'transparent' },
    dayDotToday: { backgroundColor: colors.gold },
    dayDotSelected: { backgroundColor: colors.gold2 },
    summaryCard: { marginTop: 14, padding: 18, borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadow.card },
    summaryTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    summaryEyebrow: { color: colors.gold, fontSize: 10, fontWeight: '800', letterSpacing: 1 },
    summaryTitle: { color: colors.text, fontSize: 19, fontWeight: '800', marginTop: 5 },
    percentCircle: { width: 52, height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.overlay, borderWidth: 1, borderColor: colors.gold },
    percentText: { color: colors.gold, fontSize: 13, fontWeight: '900' },
    progressTrack: { height: 6, borderRadius: 3, overflow: 'hidden', backgroundColor: colors.gsoft, marginTop: 16 },
    progressFill: { height: '100%', borderRadius: 3, backgroundColor: colors.completed },
    summaryHint: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 10 },
    section: { marginTop: 24 },
    sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 9 },
    sectionTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
    sectionIcon: { color: colors.gold, fontSize: 17 },
    sectionTitle: { color: colors.text, fontSize: 17, fontWeight: '800' },
    sectionCount: { color: colors.gold, fontSize: 12, fontWeight: '800' },
    groupCard: { paddingHorizontal: 14, borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadow.card },
    habitRow: { minHeight: 68, flexDirection: 'row', alignItems: 'center', paddingVertical: 10 },
    habitRowBorder: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    habitIconBox: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.overlay },
    habitIconBoxDone: { backgroundColor: colors.gpale },
    habitIcon: { fontSize: 19 },
    habitInfo: { flex: 1, marginLeft: 12, marginRight: 8 },
    habitLabel: { color: colors.text, fontSize: 14, fontWeight: '700', lineHeight: 19 },
    habitLabelDone: { color: colors.completed },
    habitSub: { color: colors.muted, fontSize: 11, lineHeight: 15, marginTop: 2 },
    check: { width: 26, height: 26, borderRadius: 13, borderWidth: 1.5, borderColor: colors.incomplete, alignItems: 'center', justifyContent: 'center' },
    checkDone: { backgroundColor: colors.completed, borderColor: colors.completed },
    checkMark: { color: colors.onPrimary, fontSize: 13, fontWeight: '900' },
    celebrationCard: { marginTop: 14, padding: 18, borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.gold, ...shadow.card },
    celebrationEyebrow: { color: colors.gold, fontSize: 10, fontWeight: '800', letterSpacing: 0.8 },
    celebrationTitle: { color: colors.text, fontSize: 19, fontWeight: '800', marginTop: 7 },
    celebrationSub: { color: colors.sub, fontSize: 12, marginTop: 4 },
    primaryButton: { minHeight: 46, alignItems: 'center', justifyContent: 'center', borderRadius: radius.button, backgroundColor: colors.g2, borderWidth: 1, borderColor: colors.gold, marginTop: 16 },
    primaryButtonText: { color: colors.onPrimary, fontSize: 14, fontWeight: '800' },
    shareButton: { minHeight: 42, alignItems: 'center', justifyContent: 'center', marginTop: 6 },
    shareButtonText: { color: colors.gold, fontSize: 13, fontWeight: '700' },
    savingHint: { color: colors.muted, fontSize: 11, textAlign: 'center', marginTop: 16 },
  })
}
