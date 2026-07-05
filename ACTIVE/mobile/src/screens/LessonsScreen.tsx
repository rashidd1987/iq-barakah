import { NativeStackScreenProps } from '@react-navigation/native-stack'
import React, { useCallback, useState } from 'react'
import { useFocusEffect } from '@react-navigation/native'
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import { GlobalWeek, PHASE_LABELS, WEEKS, globalWeekIndex, weekToLevelIndex } from '../data/weeks'
import { LessonsStackParamList } from '../navigation/types'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'

type Props = NativeStackScreenProps<LessonsStackParamList, 'LessonsList'>

const PHASE_ORDER: GlobalWeek['phase'][] = ['vakt', 's1', 's2', 's3']

export default function LessonsScreen({ navigation }: Props) {
  const [currentGlobalWeek, setCurrentGlobalWeek] = useState<number | null>(null)
  const [error, setError] = useState(false)

  const load = useCallback(() => {
    setError(false)
    api
      .participant()
      .then((p) => setCurrentGlobalWeek(globalWeekIndex(p.level, p.week)))
      .catch(() => setError(true))
  }, [])

  useFocusEffect(
    useCallback(() => {
      load()
    }, [load]),
  )

  if (error && currentGlobalWeek === null) {
    return <ErrorState onRetry={load} />
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {PHASE_ORDER.map((phase) => (
        <View key={phase} style={styles.section}>
          <Text style={styles.phaseTitle}>{PHASE_LABELS[phase]}</Text>
          {WEEKS.map((w, i) => {
            if (w.phase !== phase) return null
            const globalIndex = i + 1
            const done = currentGlobalWeek !== null && globalIndex < currentGlobalWeek
            const isCurrent = currentGlobalWeek !== null && globalIndex === currentGlobalWeek
            const locked = currentGlobalWeek === null || globalIndex > currentGlobalWeek
            return (
              <Pressable
                key={w.id}
                style={[styles.card, locked && styles.cardLocked, isCurrent && styles.cardCurrent]}
                disabled={locked}
                onPress={() => {
                  const { level, levelWeekIndex } = weekToLevelIndex(globalIndex)
                  navigation.navigate('LessonDetail', { level, week: levelWeekIndex, globalWeek: globalIndex })
                }}
              >
                <Text style={styles.weekIcon}>{locked ? '🔒' : done ? '✅' : w.icon}</Text>
                <View style={styles.weekInfo}>
                  <Text style={styles.weekNum}>{w.num} — {w.title}</Text>
                  <Text style={styles.weekSub}>{w.sub}</Text>
                </View>
                {isCurrent && <Text style={styles.currentBadge}>Текущий</Text>}
              </Pressable>
            )
          })}
        </View>
      ))}
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 32 },
  section: { marginBottom: 20 },
  phaseTitle: { fontSize: 13, fontWeight: '700', color: colors.sub, marginBottom: 8 },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    ...shadow.card,
  },
  cardLocked: { opacity: 0.5 },
  cardCurrent: { borderWidth: 2, borderColor: colors.gold },
  weekIcon: { fontSize: 20, marginRight: 12 },
  weekInfo: { flex: 1 },
  weekNum: { fontSize: 14, fontWeight: '600', color: colors.text },
  weekSub: { fontSize: 12, color: colors.sub, marginTop: 2 },
  currentBadge: {
    color: colors.g2,
    backgroundColor: colors.gpale,
    fontSize: 11,
    fontWeight: '600',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
})
