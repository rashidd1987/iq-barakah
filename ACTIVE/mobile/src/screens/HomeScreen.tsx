import React, { useCallback, useState } from 'react'
import { useFocusEffect } from '@react-navigation/native'
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import { LEVEL_LABELS, LEVEL_ICONS, TOTAL_STEPS, globalWeekIndex } from '../data/weeks'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'
import { computeDeeds, computeStreak, computeXP } from '../utils/stats'

export default function HomeScreen() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [level, setLevel] = useState<string | null>(null)
  const [globalWeek, setGlobalWeek] = useState(1)
  const [stats, setStats] = useState({ streak: 0, deeds: 0, xp: 0 })

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

  if (error && level === null) {
    return <ErrorState onRetry={load} />
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {level ? `${LEVEL_ICONS[level] ?? ''} ${LEVEL_LABELS[level] ?? level}` : '—'}
        </Text>
        <Text style={styles.headerSub}>Шаг {globalWeek} из {TOTAL_STEPS}</Text>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${progressPct}%` }]} />
        </View>
      </View>

      <View style={styles.statsRow}>
        <StatCard label="Стрик" value={`🔥${stats.streak}`} />
        <StatCard label="Добрые дела" value={`${stats.deeds}`} />
        <StatCard label="Баракат" value={`${stats.xp} XP`} />
      </View>
    </ScrollView>
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
  content: { padding: 16, paddingBottom: 32 },
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
  statsRow: { flexDirection: 'row', gap: 12 },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    ...shadow.card,
  },
  statCard: { flex: 1, padding: 14, alignItems: 'center' },
  statValue: { fontSize: 18, fontWeight: '700', color: colors.text },
  statLabel: { fontSize: 12, color: colors.sub, marginTop: 4 },
})
