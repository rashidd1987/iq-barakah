import { useFocusEffect } from '@react-navigation/native'
import { NativeStackScreenProps } from '@react-navigation/native-stack'
import * as WebBrowser from 'expo-web-browser'
import React, { useCallback, useMemo, useState } from 'react'
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import ScreenHeader from '../components/ScreenHeader'
import { useTheme } from '../context/ThemeContext'
import { reminderForDate } from '../data/reminders'
import { LEVEL_ICONS, LEVEL_LABELS, TOTAL_STEPS, WEEKS, globalWeekIndex } from '../data/weeks'
import { HomeStackParamList } from '../navigation/types'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { api } from '../utils/api'
import { computeDeeds, computeStreak, computeXP } from '../utils/stats'

const SHIP_URL = 'https://rashidd1987.github.io/iq-barakah/ship_barakat_business.html'

type Props = NativeStackScreenProps<HomeStackParamList, 'HomeMain'>

type HabitBuckets = {
  namaz?: Record<string, boolean>
  daily?: Record<string, boolean>
  weekly?: Record<string, boolean>
  tasks?: Record<string, boolean>
}

interface ParticipantPosition {
  level: string
  week: number
  globalWeek: number
  skill: 'I' | 'II' | 'III'
}

interface TrackerPreviewItem {
  id: string
  icon: string
  label: string
  done: boolean
}

const EXTRA_LINKS = [
  { id: 'feed', icon: '✦', title: 'Лента побед', sub: 'Прогресс джамаата' },
  { id: 'wheel', icon: '◉', title: 'Баланс', sub: 'Восемь сфер жизни' },
  { id: 'muhasaba', icon: '✎', title: 'Вечерний отчёт (Мухасаба)', sub: 'Три вопроса вечером' },
  { id: 'ship', icon: '⚓', title: 'Корабль', sub: 'Диагностика 15 отсеков' },
] as const

function localDateKey(date = new Date()): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function greeting(hour: number): string {
  if (hour < 5) return 'Доброй ночи'
  if (hour < 12) return 'Доброе утро'
  if (hour < 18) return 'Добрый день'
  return 'Добрый вечер'
}

export default function HomeScreen({ navigation }: Props) {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [position, setPosition] = useState<ParticipantPosition | null>(null)
  const [todayHabits, setTodayHabits] = useState<HabitBuckets>({})
  const [lessonTitle, setLessonTitle] = useState<string | null>(null)
  const [lessonTasksDone, setLessonTasksDone] = useState(false)
  const [stats, setStats] = useState({ streak: 0, deeds: 0, xp: 0 })
  const [cohortCount, setCohortCount] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [participant, records] = await Promise.all([api.participant(), api.tracker(30)])
      const globalWeek = globalWeekIndex(participant.level, participant.week)
      const skill = (['I', 'II', 'III'].includes(participant.vakt_level ?? '') ? participant.vakt_level : 'I') as
        | 'I'
        | 'II'
        | 'III'
      const nextPosition = { level: participant.level, week: participant.week, globalWeek, skill }
      setPosition(nextPosition)

      const todayRecord = records.find((record) => record.date === localDateKey())
      const habits = (todayRecord?.habits ?? {}) as HabitBuckets
      setTodayHabits(habits)

      const streak = computeStreak(records)
      const deeds = computeDeeds(records)
      setStats({ streak, deeds, xp: computeXP(streak, Math.max(0, globalWeek - 1), deeds) })
      setError(false)

      api
        .content(participant.level, participant.week)
        .then((content) => {
          setLessonTitle(content.title)
          const tasks = content.tasks[skill] ?? []
          const taskState = habits.tasks ?? {}
          setLessonTasksDone(tasks.length > 0 && tasks.every((_, index) => taskState[String(index)]))
        })
        .catch(() => {
          setLessonTitle(null)
          setLessonTasksDone(false)
        })

      api.cohortCount().then((result) => setCohortCount(result.count)).catch(() => setCohortCount(null))
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useFocusEffect(
    useCallback(() => {
      load()
    }, [load]),
  )

  if (error && position === null) return <ErrorState onRetry={load} />

  const now = new Date()
  const currentWeek = position?.globalWeek ?? 1
  const weekData = WEEKS[currentWeek - 1]
  const previousWeek = currentWeek > 1 ? WEEKS[currentWeek - 2] : null
  const nextWeek = currentWeek < TOTAL_STEPS ? WEEKS[currentWeek] : null
  const progressPct = Math.min(100, Math.round((currentWeek / TOTAL_STEPS) * 100))
  const reminder = reminderForDate(now)

  const trackerItems: TrackerPreviewItem[] = [
    { id: 'fajr', icon: '☀︎', label: 'Фаджр', done: !!todayHabits.namaz?.fajr },
    { id: 'quran', icon: '▤', label: 'Коран', done: !!todayHabits.daily?.quran },
    { id: 'azkar', icon: '◌', label: 'Утренний зикр', done: !!todayHabits.daily?.azkar_m },
    {
      id: 'lesson',
      icon: '◇',
      label: 'Урок IQ Barakah',
      done: lessonTasksDone || !!todayHabits.weekly?.lesson,
    },
  ]
  const trackerDone = trackerItems.filter((item) => item.done).length

  const openLesson = () => {
    if (!position) return
    navigation.getParent<any>()?.navigate('Lessons', {
      screen: 'LessonDetail',
      params: { level: position.level, week: position.week, globalWeek: position.globalWeek },
    })
  }

  const openExtra = (id: (typeof EXTRA_LINKS)[number]['id']) => {
    if (id === 'feed') navigation.navigate('ActivityFeed')
    if (id === 'wheel') navigation.getParent<any>()?.navigate('Wheel')
    if (id === 'muhasaba') navigation.navigate('Muhasaba')
    if (id === 'ship') void WebBrowser.openBrowserAsync(SHIP_URL)
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.gold} />}
    >
      <ScreenHeader badge="Главная" title="Ассаляму алейкум" subtitle={greeting(now.getHours())}>
        <View style={styles.headerStats}>
          <View style={styles.headerStat}>
            <Text style={styles.headerStatIcon}>◆</Text>
            <Text style={styles.headerStatValue}>{stats.streak}</Text>
            <Text style={styles.headerStatLabel}>дней</Text>
          </View>
          <View style={styles.headerStat}>
            <Text style={styles.headerStatIcon}>✦</Text>
            <Text style={styles.headerStatValue}>{stats.xp}</Text>
            <Text style={styles.headerStatLabel}>баллов</Text>
          </View>
        </View>
      </ScreenHeader>

      <View style={styles.body}>
        <View style={styles.lessonCard}>
          <View style={styles.lessonEyebrowRow}>
            <Text style={styles.lessonEyebrow}>
              {position ? `${LEVEL_ICONS[position.level] ?? '◆'} ${LEVEL_LABELS[position.level] ?? position.level}` : 'IQ BARAKAH'}
            </Text>
            <Text style={styles.lessonDuration}>5 минут</Text>
          </View>
          <Text style={styles.lessonTitle}>Шаг {currentWeek} · {lessonTitle || weekData?.title || 'Текущий урок'}</Text>
          <Text style={styles.lessonSubtitle}>{weekData?.sub || 'Продолжите свой путь'}</Text>
          <View style={styles.lessonProgressMeta}>
            <Text style={styles.lessonProgressValue}>{currentWeek} из {TOTAL_STEPS}</Text>
            <Text style={styles.lessonProgressPercent}>{progressPct}%</Text>
          </View>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${progressPct}%` }]} />
          </View>
          <Pressable accessibilityRole="button" style={styles.continueButton} onPress={openLesson}>
            <Text style={styles.continueButtonText}>Продолжить</Text>
          </Pressable>
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Трекер на сегодня</Text>
          <Pressable onPress={() => navigation.getParent<any>()?.navigate('Tracker')} hitSlop={8}>
            <Text style={styles.sectionLink}>Все привычки ›</Text>
          </Pressable>
        </View>
        <Pressable style={styles.trackerCard} onPress={() => navigation.getParent<any>()?.navigate('Tracker')}>
          {trackerItems.map((item, index) => (
            <View key={item.id} style={[styles.trackerRow, index < trackerItems.length - 1 && styles.trackerRowBorder]}>
              <View style={styles.trackerIconBox}><Text style={styles.trackerIcon}>{item.icon}</Text></View>
              <Text style={[styles.trackerLabel, item.done && styles.trackerLabelDone]}>{item.label}</Text>
              <View style={[styles.trackerCheck, item.done && styles.trackerCheckDone]}>
                {item.done && <Text style={styles.trackerCheckMark}>✓</Text>}
              </View>
            </View>
          ))}
          <View style={styles.trackerProgressRow}>
            <Text style={styles.trackerProgressValue}>{trackerDone} из {trackerItems.length}</Text>
            <View style={styles.trackerProgressTrack}>
              <View style={[styles.trackerProgressFill, { width: `${(trackerDone / trackerItems.length) * 100}%` }]} />
            </View>
          </View>
        </Pressable>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Ваш путь</Text>
          <Pressable onPress={() => navigation.getParent<any>()?.navigate('Lessons')} hitSlop={8}>
            <Text style={styles.sectionLink}>Все шаги ›</Text>
          </Pressable>
        </View>
        <View style={styles.pathCard}>
          <PathNode icon={previousWeek ? '✓' : '•'} title={previousWeek?.title || 'Начало'} sub={previousWeek ? 'Урок завершён' : 'Путь начат'} state="done" />
          <View style={styles.pathLine} />
          <PathNode icon={String(currentWeek)} title={weekData?.title || 'Текущий шаг'} sub="Текущий урок" state="current" />
          <View style={styles.pathLine} />
          <PathNode icon="⌑" title={nextWeek?.title || 'Завершение'} sub={nextWeek ? 'Откроется позже' : 'Путь завершён'} state="locked" />
        </View>

        {cohortCount !== null && cohortCount > 0 && (
          <Text style={styles.cohortText}>С вами на этом шаге ещё {cohortCount} участников</Text>
        )}

        <View style={styles.reminderCard}>
          <View style={styles.reminderIcon}><Text style={styles.reminderIconText}>☾</Text></View>
          <View style={styles.reminderContent}>
            <Text style={styles.reminderEyebrow}>Напоминание дня</Text>
            <Text style={styles.reminderText}>«{reminder.text}»</Text>
            <Text style={styles.reminderSource}>{reminder.source}</Text>
          </View>
        </View>

        <Text style={[styles.sectionTitle, styles.moreTitle]}>Ещё</Text>
        <View style={styles.extraGrid}>
          {EXTRA_LINKS.map((item) => (
            <Pressable key={item.id} style={styles.extraCard} onPress={() => openExtra(item.id)}>
              <Text style={styles.extraIcon}>{item.icon}</Text>
              <Text style={styles.extraTitle}>{item.title}</Text>
              <Text style={styles.extraSub}>{item.sub}</Text>
            </Pressable>
          ))}
        </View>
      </View>
    </ScrollView>
  )
}

function PathNode({ icon, title, sub, state }: { icon: string; title: string; sub: string; state: 'done' | 'current' | 'locked' }) {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  return (
    <View style={styles.pathNode}>
      <View style={[styles.pathCircle, state === 'done' && styles.pathCircleDone, state === 'current' && styles.pathCircleCurrent]}>
        <Text style={[styles.pathCircleText, state === 'done' && styles.pathCircleTextDone, state === 'current' && styles.pathCircleTextCurrent]}>{icon}</Text>
      </View>
      <Text numberOfLines={2} style={[styles.pathTitle, state === 'locked' && styles.pathTextLocked]}>{title}</Text>
      <Text numberOfLines={2} style={[styles.pathSub, state === 'done' && styles.pathSubDone, state === 'current' && styles.pathSubCurrent]}>{sub}</Text>
    </View>
  )
}

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    content: { paddingBottom: 32 },
    body: { paddingHorizontal: 16, paddingTop: 16 },
    headerStats: { flexDirection: 'row', gap: 10, marginTop: 18 },
    headerStat: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      paddingVertical: 8,
      paddingHorizontal: 12,
      borderRadius: 999,
      backgroundColor: 'rgba(255,255,255,0.11)',
      borderWidth: 1,
      borderColor: 'rgba(255,255,255,0.18)',
    },
    headerStatIcon: { color: colors.gold2, fontSize: 12 },
    headerStatValue: { color: colors.onPrimary, fontSize: 14, fontWeight: '800' },
    headerStatLabel: { color: 'rgba(255,255,255,0.72)', fontSize: 12 },
    lessonCard: {
      backgroundColor: colors.card,
      borderRadius: 22,
      borderWidth: 1,
      borderColor: colors.border,
      padding: 20,
      ...shadow.card,
    },
    lessonEyebrowRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    lessonEyebrow: { color: colors.gold, fontSize: 12, fontWeight: '800', letterSpacing: 0.6, textTransform: 'uppercase' },
    lessonDuration: { color: colors.muted, fontSize: 12 },
    lessonTitle: { color: colors.text, fontSize: 23, fontWeight: '800', lineHeight: 29, marginTop: 18 },
    lessonSubtitle: { color: colors.sub, fontSize: 13, lineHeight: 19, marginTop: 6 },
    lessonProgressMeta: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 20, marginBottom: 8 },
    lessonProgressValue: { color: colors.gold, fontSize: 14, fontWeight: '800' },
    lessonProgressPercent: { color: colors.muted, fontSize: 12 },
    progressTrack: { height: 6, borderRadius: 3, overflow: 'hidden', backgroundColor: colors.gsoft },
    progressFill: { height: '100%', borderRadius: 3, backgroundColor: colors.gold },
    continueButton: {
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 52,
      marginTop: 20,
      borderRadius: radius.button,
      backgroundColor: colors.g2,
      borderWidth: 1,
      borderColor: colors.gold,
    },
    continueButtonText: { color: colors.onPrimary, fontSize: 16, fontWeight: '800' },
    sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 24, marginBottom: 10 },
    sectionTitle: { color: colors.text, fontSize: 19, fontWeight: '800' },
    sectionLink: { color: colors.gold, fontSize: 13, fontWeight: '700' },
    trackerCard: {
      backgroundColor: colors.card,
      borderRadius: radius.card,
      borderWidth: 1,
      borderColor: colors.border,
      paddingHorizontal: 14,
      paddingTop: 4,
      paddingBottom: 14,
      ...shadow.card,
    },
    trackerRow: { minHeight: 58, flexDirection: 'row', alignItems: 'center' },
    trackerRowBorder: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    trackerIconBox: { width: 34, alignItems: 'center' },
    trackerIcon: { color: colors.gold, fontSize: 22 },
    trackerLabel: { flex: 1, marginLeft: 10, color: colors.text, fontSize: 14, fontWeight: '600' },
    trackerLabelDone: { color: colors.completed },
    trackerCheck: { width: 24, height: 24, borderRadius: 12, borderWidth: 1.5, borderColor: colors.incomplete, alignItems: 'center', justifyContent: 'center' },
    trackerCheckDone: { backgroundColor: colors.completed, borderColor: colors.completed },
    trackerCheckMark: { color: colors.onPrimary, fontSize: 13, fontWeight: '900' },
    trackerProgressRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 12 },
    trackerProgressValue: { minWidth: 36, color: colors.gold, fontSize: 13, fontWeight: '800' },
    trackerProgressTrack: { flex: 1, height: 5, borderRadius: 3, overflow: 'hidden', backgroundColor: colors.gsoft },
    trackerProgressFill: { height: '100%', borderRadius: 3, backgroundColor: colors.completed },
    pathCard: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      backgroundColor: colors.card,
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radius.card,
      paddingHorizontal: 12,
      paddingVertical: 18,
      ...shadow.card,
    },
    pathNode: { width: '28%', alignItems: 'center' },
    pathLine: { flex: 1, height: 1, marginTop: 23, backgroundColor: colors.gold },
    pathCircle: { width: 48, height: 48, borderRadius: 24, borderWidth: 1.5, borderColor: colors.incomplete, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.cardRaised },
    pathCircleDone: { borderColor: colors.completed, backgroundColor: colors.gpale },
    pathCircleCurrent: { borderColor: colors.gold, borderWidth: 2, backgroundColor: colors.overlay, shadowColor: colors.gold, shadowOpacity: 0.24, shadowRadius: 10, elevation: 3 },
    pathCircleText: { color: colors.incomplete, fontSize: 16, fontWeight: '800' },
    pathCircleTextDone: { color: colors.completed },
    pathCircleTextCurrent: { color: colors.gold },
    pathTitle: { color: colors.text, fontSize: 12, fontWeight: '700', textAlign: 'center', lineHeight: 16, marginTop: 8 },
    pathTextLocked: { color: colors.muted },
    pathSub: { color: colors.muted, fontSize: 10, textAlign: 'center', lineHeight: 14, marginTop: 3 },
    pathSubDone: { color: colors.completed },
    pathSubCurrent: { color: colors.gold },
    cohortText: { color: colors.muted, fontSize: 12, textAlign: 'center', marginTop: 10 },
    reminderCard: {
      flexDirection: 'row',
      gap: 14,
      marginTop: 24,
      padding: 18,
      borderRadius: radius.card,
      backgroundColor: colors.card,
      borderWidth: 1,
      borderColor: colors.border,
      ...shadow.card,
    },
    reminderIcon: { width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.overlay },
    reminderIconText: { color: colors.gold, fontSize: 26 },
    reminderContent: { flex: 1 },
    reminderEyebrow: { color: colors.gold, fontSize: 11, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.8 },
    reminderText: { color: colors.text, fontSize: 15, fontWeight: '600', lineHeight: 22, marginTop: 8 },
    reminderSource: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 8 },
    moreTitle: { marginTop: 24, marginBottom: 10 },
    extraGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
    extraCard: { width: '48.5%', minHeight: 112, padding: 14, borderRadius: radius.button, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
    extraIcon: { color: colors.gold, fontSize: 22 },
    extraTitle: { color: colors.text, fontSize: 14, fontWeight: '700', marginTop: 10 },
    extraSub: { color: colors.muted, fontSize: 11, lineHeight: 15, marginTop: 3 },
  })
}
