import { NativeStackScreenProps } from '@react-navigation/native-stack'
import * as WebBrowser from 'expo-web-browser'
import React, { useCallback, useState } from 'react'
import { useFocusEffect } from '@react-navigation/native'
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import ScreenHeader from '../components/ScreenHeader'
import { useAuth } from '../context/AuthContext'
import { HomeStackParamList } from '../navigation/types'
import { LEVEL_LABELS, LEVEL_ICONS, TOTAL_STEPS, globalWeekIndex } from '../data/weeks'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'
import { computeDeeds, computeStreak, computeXP } from '../utils/stats'

// Same hosted diagnostic the miniapp itself links out to (ACTIVE/site/miniapp.html
// opens the exact same URL) — 15-compartment "Корабль Бараката" business/personal
// assessment. Not worth re-implementing natively; opening it in-app is the parity move.
const SHIP_URL = 'https://rashidd1987.github.io/iq-barakah/ship_barakat_business.html'

const QUICK_LINKS = [
  { id: 'tracker', icon: '📋', title: 'Трекер дня', sub: 'Намаз, поминание, самоотчёт' },
  { id: 'lessons', icon: '📚', title: 'Текущий урок', sub: 'Открыть карту уроков' },
  { id: 'feed', icon: '🎉', title: 'Лента побед', sub: 'Кто из джамаата что прошёл' },
  { id: 'wheel', icon: '🎯', title: 'Колесо баланса', sub: '8 сфер жизни' },
  { id: 'muhasaba', icon: '✍️', title: 'Вечерний самоотчёт', sub: 'Мухасаба — три вопроса · 2 минуты' },
  { id: 'diag', icon: '🎯', title: 'Диагностика уровня', sub: 'Пройти заново' },
  { id: 'ship', icon: '⚓', title: 'Корабль Бараката', sub: '15 отсеков · бизнес и личная жизнь' },
] as const

const RITUALS = [
  { hour: 6, minute: 0, label: 'утреннего поминания' },
  { hour: 13, minute: 30, label: 'обеденного намаза' },
  { hour: 20, minute: 0, label: 'вечернего поминания' },
  { hour: 22, minute: 0, label: 'вечернего разбора' },
]

function greeting(hour: number): string {
  if (hour < 5) return 'Доброй ночи'
  if (hour < 12) return 'Доброе утро'
  if (hour < 18) return 'Добрый день'
  return 'Добрый вечер'
}

function nextRitual(now: Date): { label: string; minutesUntil: number } {
  const nowMinutes = now.getHours() * 60 + now.getMinutes()
  for (const r of RITUALS) {
    const ritualMinutes = r.hour * 60 + r.minute
    if (ritualMinutes > nowMinutes) {
      return { label: r.label, minutesUntil: ritualMinutes - nowMinutes }
    }
  }
  // Past the last ritual today — next one is tomorrow's first.
  const first = RITUALS[0]
  return { label: first.label, minutesUntil: 24 * 60 - nowMinutes + first.hour * 60 + first.minute }
}

function formatCountdown(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m} мин`
  return `${h} ч ${m} мин`
}

type Props = NativeStackScreenProps<HomeStackParamList, 'HomeMain'>

export default function HomeScreen({ navigation }: Props) {
  const { resetOnboarding } = useAuth()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [level, setLevel] = useState<string | null>(null)
  const [globalWeek, setGlobalWeek] = useState(1)
  const [stats, setStats] = useState({ streak: 0, deeds: 0, xp: 0 })
  const [cohortCount, setCohortCount] = useState<number | null>(null)
  const [missions, setMissions] = useState({ habitsDone: false, stepDone: false, muhasabaDone: false })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [participant, records] = await Promise.all([api.participant(), api.tracker(30)])
      setLevel(participant.level)
      const gw = globalWeekIndex(participant.level, participant.week)
      setGlobalWeek(gw)
      const streak = computeStreak(records)
      const deeds = computeDeeds(records)
      setStats({ streak, deeds, xp: computeXP(streak, gw - 1, deeds) })
      setError(false)
      // Best-effort — the jamaat count is a nice-to-have, not worth blocking the screen over.
      api.cohortCount().then((r) => setCohortCount(r.count)).catch(() => setCohortCount(null))

      // "Миссии дня" — best-effort, doesn't block the main screen if it fails.
      const todayKey = new Date().toISOString().slice(0, 10)
      const todayRecord = records.find((r) => r.date === todayKey)
      const habitsDone = !!todayRecord && Object.values({
        ...todayRecord.habits.namaz,
        ...todayRecord.habits.daily,
      }).some(Boolean)
      api
        .content(participant.level, participant.week)
        .then((content) => {
          const skill = (participant.vakt_level as 'I' | 'II' | 'III') || 'I'
          const tasks = content.tasks[skill] ?? []
          const taskState = (todayRecord?.habits as { tasks?: Record<string, boolean> } | undefined)?.tasks ?? {}
          const stepDone = tasks.length > 0 && tasks.every((_, i) => taskState[String(i)])
          setMissions((m) => ({ ...m, habitsDone, stepDone }))
        })
        .catch(() => setMissions((m) => ({ ...m, habitsDone })))
      api.muhasabaStreak().then((r) => setMissions((m) => ({ ...m, muhasabaDone: r.done_today }))).catch(() => {})
    } catch {
      // keep any previously loaded data on screen — only show the error state if we have nothing yet
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

  const progressPct = Math.min(100, Math.round(((globalWeek - 1) / TOTAL_STEPS) * 100))

  const handleQuickLink = (id: (typeof QUICK_LINKS)[number]['id']) => {
    switch (id) {
      case 'tracker':
        navigation.getParent()?.navigate('Tracker')
        break
      case 'lessons':
        navigation.getParent()?.navigate('Lessons')
        break
      case 'feed':
        navigation.navigate('ActivityFeed')
        break
      case 'wheel':
        navigation.getParent()?.navigate('Wheel')
        break
      case 'muhasaba':
        navigation.navigate('Muhasaba')
        break
      case 'diag':
        resetOnboarding()
        break
      case 'ship':
        WebBrowser.openBrowserAsync(SHIP_URL)
        break
    }
  }

  if (error && level === null) {
    return <ErrorState onRetry={load} />
  }

  const now = new Date()
  const ritual = nextRitual(now)

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      <ScreenHeader
        badge="Главная"
        title={`${greeting(now.getHours())} 👋`}
        subtitle={`До ${ritual.label}: ${formatCountdown(ritual.minutesUntil)}`}
      />

      <View style={styles.body}>
      <View style={styles.streakHero}>
        <Text style={styles.streakFlame}>🔥</Text>
        <Text style={styles.streakNumber}>{stats.streak}</Text>
        <Text style={styles.streakLabel}>
          {stats.streak > 0 ? 'дней подряд без перерыва' : 'начни сегодня — без системы осознанность держится 2-3 дня'}
        </Text>
      </View>

      <Text style={styles.quickLinksTitle}>Миссии дня</Text>
      <View style={styles.missionsCard}>
        <MissionRow
          label="Отметь привычки дня"
          done={missions.habitsDone}
          onPress={() => navigation.getParent()?.navigate('Tracker')}
        />
        <MissionRow
          label={`Заверши шаг ${globalWeek}`}
          done={missions.stepDone}
          onPress={() => navigation.getParent()?.navigate('Tracker')}
        />
        <MissionRow
          label="Вечерний самоотчёт"
          done={missions.muhasabaDone}
          onPress={() => navigation.navigate('Muhasaba')}
        />
      </View>

      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {level ? `${LEVEL_ICONS[level] ?? ''} ${LEVEL_LABELS[level] ?? level}` : '—'}
        </Text>
        <Text style={styles.headerSub}>Шаг {globalWeek} из {TOTAL_STEPS}</Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${progressPct}%` }]} />
        </View>
      </View>

      {cohortCount !== null && cohortCount > 0 && (
        <View style={styles.cohortCard}>
          <Text style={styles.cohortText}>
            🤝 С тобой ещё {cohortCount} {pluralBrothers(cohortCount)} на этом шаге
          </Text>
        </View>
      )}

      <View style={styles.statsRow}>
        <StatCard label="Добрые дела" value={`${stats.deeds}`} />
        <StatCard label="Баракат" value={`${stats.xp} XP`} />
      </View>

      <Text style={styles.quickLinksTitle}>Перейти</Text>
      <View style={styles.quickLinks}>
        {QUICK_LINKS.map((item) => (
          <Pressable key={item.id} style={styles.quickLinkRow} onPress={() => handleQuickLink(item.id)}>
            <Text style={styles.quickLinkIcon}>{item.icon}</Text>
            <View style={styles.quickLinkInfo}>
              <Text style={styles.quickLinkLabel}>{item.title}</Text>
              <Text style={styles.quickLinkSub}>{item.sub}</Text>
            </View>
            <Text style={styles.quickLinkArrow}>›</Text>
          </Pressable>
        ))}
      </View>
      </View>
    </ScrollView>
  )
}

function pluralBrothers(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'брат'
  if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) return 'брата'
  return 'братьев'
}

function MissionRow({ label, done, onPress }: { label: string; done: boolean; onPress: () => void }) {
  return (
    <Pressable style={styles.missionRow} onPress={onPress}>
      <View style={[styles.missionCheck, done && styles.missionCheckDone]}>
        {done && <Text style={styles.missionCheckMark}>✓</Text>}
      </View>
      <Text style={[styles.missionLabel, done && styles.missionLabelDone]}>{label}</Text>
    </Pressable>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <View style={[styles.card, styles.statCard]}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { paddingBottom: 32 },
  body: { padding: 16, marginTop: -16 },
  streakHero: {
    alignItems: 'center',
    backgroundColor: colors.g1,
    borderRadius: radius.card,
    paddingVertical: 28,
    marginBottom: 16,
    ...shadow.card,
  },
  streakFlame: { fontSize: 40 },
  streakNumber: { fontSize: 48, fontWeight: '800', color: colors.gold, marginTop: -4 },
  streakLabel: { fontSize: 13, color: colors.goldpale, marginTop: 4, textAlign: 'center', paddingHorizontal: 24 },
  header: {
    backgroundColor: colors.g2,
    borderRadius: radius.card,
    padding: 20,
    marginBottom: 16,
  },
  headerTitle: { color: '#fff', fontSize: 20, fontWeight: '700' },
  headerSub: { color: colors.goldpale, fontSize: 14, marginTop: 4, marginBottom: 12 },
  progressTrack: { height: 8, backgroundColor: 'rgba(255,255,255,0.25)', borderRadius: 4, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: colors.gold },
  cohortCard: {
    backgroundColor: colors.gpale,
    borderRadius: radius.card,
    padding: 14,
    marginBottom: 16,
  },
  cohortText: { fontSize: 14, fontWeight: '600', color: colors.g2, textAlign: 'center' },
  statsRow: { flexDirection: 'row', gap: 12 },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    ...shadow.card,
  },
  statCard: { flex: 1, padding: 14, alignItems: 'center' },
  statValue: { fontSize: 18, fontWeight: '700', color: colors.text },
  statLabel: { fontSize: 12, color: colors.sub, marginTop: 4 },
  missionsCard: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 8,
    marginBottom: 16,
    ...shadow.card,
  },
  missionRow: { flexDirection: 'row', alignItems: 'center', padding: 8 },
  missionCheck: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  missionCheckDone: { backgroundColor: colors.g2, borderColor: colors.g2 },
  missionCheckMark: { color: '#fff', fontSize: 12, fontWeight: '700' },
  missionLabel: { fontSize: 14, color: colors.text, fontWeight: '600' },
  missionLabelDone: { color: colors.muted, textDecorationLine: 'line-through' },
  quickLinksTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginTop: 24,
    marginBottom: 8,
  },
  quickLinks: { gap: 8 },
  quickLinkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 12,
    ...shadow.card,
  },
  quickLinkIcon: { fontSize: 22, marginRight: 12 },
  quickLinkInfo: { flex: 1 },
  quickLinkLabel: { fontSize: 14, fontWeight: '600', color: colors.text },
  quickLinkSub: { fontSize: 12, color: colors.sub, marginTop: 2 },
  quickLinkArrow: { fontSize: 20, color: colors.muted },
})
