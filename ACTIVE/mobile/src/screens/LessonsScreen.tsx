import { useFocusEffect } from '@react-navigation/native'
import { NativeStackScreenProps } from '@react-navigation/native-stack'
import React, { useCallback, useMemo, useState } from 'react'
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import ScreenHeader from '../components/ScreenHeader'
import { useTheme } from '../context/ThemeContext'
import { GlobalWeek, PHASE_LABELS, TOTAL_STEPS, WEEKS, globalWeekIndex, weekToLevelIndex } from '../data/weeks'
import { LessonsStackParamList } from '../navigation/types'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { api } from '../utils/api'

type Props = NativeStackScreenProps<LessonsStackParamList, 'LessonsList'>
type PhaseFilter = 'all' | GlobalWeek['phase']

const PHASE_ORDER: GlobalWeek['phase'][] = ['vakt', 's1', 's2', 's3']
const FILTERS: { key: PhaseFilter; label: string }[] = [
  { key: 'all', label: 'Весь путь' },
  { key: 'vakt', label: 'Старт' },
  { key: 's1', label: 'Сезон 1' },
  { key: 's2', label: 'Сезон 2' },
  { key: 's3', label: 'Сезон 3' },
]

function compactPhaseLabel(phase: GlobalWeek['phase']): string {
  if (phase === 'vakt') return 'IQ Barakah Старт · 6 шагов'
  if (phase === 's1') return 'Сезон 1 · Основание'
  if (phase === 's2') return 'Сезон 2 · Строительство'
  return 'Сезон 3 · Наследие'
}

export default function LessonsScreen({ navigation }: Props) {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const [currentGlobalWeek, setCurrentGlobalWeek] = useState<number | null>(null)
  const [error, setError] = useState(false)
  const [filter, setFilter] = useState<PhaseFilter>('all')

  const load = useCallback(() => {
    setError(false)
    api.participant()
      .then((participant) => setCurrentGlobalWeek(globalWeekIndex(participant.level, participant.week)))
      .catch(() => setError(true))
  }, [])

  useFocusEffect(useCallback(() => { load() }, [load]))
  if (error && currentGlobalWeek === null) return <ErrorState onRetry={load} />

  const completed = currentGlobalWeek ? Math.max(0, currentGlobalWeek - 1) : 0
  const progressPct = Math.round((completed / TOTAL_STEPS) * 100)
  const visiblePhases = filter === 'all' ? PHASE_ORDER : [filter]

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <ScreenHeader badge="Обучение" title="Ваш путь" subtitle="30 последовательных шагов">
        <View style={styles.headerProgressRow}>
          <Text style={styles.headerProgressText}>{completed} из {TOTAL_STEPS} завершено</Text>
          <Text style={styles.headerProgressPercent}>{progressPct}%</Text>
        </View>
        <View style={styles.headerProgressTrack}><View style={[styles.headerProgressFill, { width: `${progressPct}%` }]} /></View>
      </ScreenHeader>

      <View style={styles.body}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
          {FILTERS.map((item) => {
            const selected = filter === item.key
            return (
              <Pressable
                key={item.key}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                style={[styles.filterChip, selected && styles.filterChipSelected]}
                onPress={() => setFilter(item.key)}
              >
                <Text style={[styles.filterText, selected && styles.filterTextSelected]}>{item.label}</Text>
              </Pressable>
            )
          })}
        </ScrollView>

        {visiblePhases.map((phase) => {
          const phaseWeeks = WEEKS.map((week, index) => ({ week, globalIndex: index + 1 })).filter(({ week }) => week.phase === phase)
          const phaseDone = phaseWeeks.filter(({ globalIndex }) => currentGlobalWeek !== null && globalIndex < currentGlobalWeek).length
          return (
            <View key={phase} style={styles.phaseSection}>
              <View style={styles.phaseHeader}>
                <View style={styles.phaseNumber}><Text style={styles.phaseNumberText}>{PHASE_ORDER.indexOf(phase) + 1}</Text></View>
                <View style={styles.phaseInfo}>
                  <Text style={styles.phaseTitle}>{compactPhaseLabel(phase)}</Text>
                  <Text style={styles.phaseSub}>{phaseDone} из {phaseWeeks.length} шагов завершено</Text>
                </View>
              </View>

              <View style={styles.pathList}>
                {phaseWeeks.map(({ week, globalIndex }, index) => {
                  const done = currentGlobalWeek !== null && globalIndex < currentGlobalWeek
                  const current = currentGlobalWeek !== null && globalIndex === currentGlobalWeek
                  const locked = currentGlobalWeek === null || globalIndex > currentGlobalWeek
                  return (
                    <View key={week.id} style={styles.pathRow}>
                      <View style={styles.rail}>
                        {index > 0 && <View style={[styles.railLineTop, (done || current) && styles.railLineActive]} />}
                        <View style={[styles.node, done && styles.nodeDone, current && styles.nodeCurrent]}>
                          <Text style={[styles.nodeText, done && styles.nodeTextDone, current && styles.nodeTextCurrent]}>
                            {done ? '✓' : current ? String(globalIndex) : '⌑'}
                          </Text>
                        </View>
                        {index < phaseWeeks.length - 1 && <View style={[styles.railLineBottom, done && styles.railLineActive]} />}
                      </View>

                      <Pressable
                        accessibilityRole="button"
                        accessibilityState={{ disabled: locked }}
                        disabled={locked}
                        style={[styles.lessonCard, done && styles.lessonCardDone, current && styles.lessonCardCurrent, locked && styles.lessonCardLocked]}
                        onPress={() => {
                          const { level, levelWeekIndex } = weekToLevelIndex(globalIndex)
                          navigation.navigate('LessonDetail', { level, week: levelWeekIndex, globalWeek: globalIndex })
                        }}
                      >
                        <View style={styles.lessonTopRow}>
                          <Text style={[styles.lessonNumber, current && styles.lessonNumberCurrent]}>{week.num}</Text>
                          {done && <Text style={styles.doneBadge}>Завершён</Text>}
                          {current && <Text style={styles.currentBadge}>Текущий шаг</Text>}
                          {locked && <Text style={styles.lockedBadge}>Закрыт</Text>}
                        </View>
                        <Text style={[styles.lessonTitle, locked && styles.lessonTextLocked]}>{week.title}</Text>
                        <Text style={[styles.lessonSub, locked && styles.lessonTextLocked]}>{week.sub}</Text>
                        {current && <Text style={styles.continueText}>Продолжить ›</Text>}
                      </Pressable>
                    </View>
                  )
                })}
              </View>
            </View>
          )
        })}

        <View style={styles.pathNote}>
          <Text style={styles.pathNoteIcon}>◇</Text>
          <Text style={styles.pathNoteText}>Следующий шаг открывается после завершения текущего. Ваш прогресс сохраняется в общей системе IQ Barakah.</Text>
        </View>
      </View>
    </ScrollView>
  )
}

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    content: { paddingBottom: 36 },
    body: { paddingHorizontal: 16, paddingTop: 14 },
    headerProgressRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 18, marginBottom: 8 },
    headerProgressText: { color: colors.onPrimary, fontSize: 12, fontWeight: '700' },
    headerProgressPercent: { color: colors.gold2, fontSize: 12, fontWeight: '900' },
    headerProgressTrack: { height: 6, overflow: 'hidden', borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.18)' },
    headerProgressFill: { height: '100%', borderRadius: 3, backgroundColor: colors.gold2 },
    filters: { gap: 8, paddingVertical: 2, paddingRight: 16 },
    filterChip: { minHeight: 38, justifyContent: 'center', paddingHorizontal: 14, borderRadius: 19, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
    filterChipSelected: { backgroundColor: colors.g2, borderColor: colors.gold },
    filterText: { color: colors.sub, fontSize: 12, fontWeight: '700' },
    filterTextSelected: { color: colors.onPrimary },
    phaseSection: { marginTop: 24 },
    phaseHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
    phaseNumber: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.overlay, borderWidth: 1, borderColor: colors.gold },
    phaseNumberText: { color: colors.gold, fontSize: 14, fontWeight: '900' },
    phaseInfo: { flex: 1, marginLeft: 11 },
    phaseTitle: { color: colors.text, fontSize: 17, fontWeight: '800' },
    phaseSub: { color: colors.muted, fontSize: 11, marginTop: 3 },
    pathList: { gap: 0 },
    pathRow: { flexDirection: 'row', alignItems: 'stretch' },
    rail: { width: 42, alignItems: 'center' },
    railLineTop: { position: 'absolute', top: 0, width: 1.5, height: 20, backgroundColor: colors.border },
    railLineBottom: { position: 'absolute', top: 48, bottom: 0, width: 1.5, backgroundColor: colors.border },
    railLineActive: { backgroundColor: colors.gold },
    node: { width: 34, height: 34, borderRadius: 17, marginTop: 15, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: colors.incomplete, backgroundColor: colors.bg, zIndex: 2 },
    nodeDone: { borderColor: colors.completed, backgroundColor: colors.gpale },
    nodeCurrent: { borderColor: colors.gold, borderWidth: 2, backgroundColor: colors.card, shadowColor: colors.gold, shadowOpacity: 0.25, shadowRadius: 9, elevation: 3 },
    nodeText: { color: colors.incomplete, fontSize: 12, fontWeight: '900' },
    nodeTextDone: { color: colors.completed },
    nodeTextCurrent: { color: colors.gold },
    lessonCard: { flex: 1, minHeight: 116, marginLeft: 8, marginBottom: 10, padding: 15, borderRadius: radius.button, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, ...shadow.card },
    lessonCardDone: { backgroundColor: colors.card, borderColor: colors.gsoft },
    lessonCardCurrent: { borderColor: colors.gold, backgroundColor: colors.cardRaised },
    lessonCardLocked: { opacity: 0.58, shadowOpacity: 0, elevation: 0 },
    lessonTopRow: { minHeight: 20, flexDirection: 'row', alignItems: 'center' },
    lessonNumber: { color: colors.muted, fontSize: 10, fontWeight: '800', letterSpacing: 0.5 },
    lessonNumberCurrent: { color: colors.gold },
    doneBadge: { marginLeft: 'auto', color: colors.completed, fontSize: 10, fontWeight: '800' },
    currentBadge: { marginLeft: 'auto', color: colors.gold, fontSize: 10, fontWeight: '800' },
    lockedBadge: { marginLeft: 'auto', color: colors.muted, fontSize: 10, fontWeight: '700' },
    lessonTitle: { color: colors.text, fontSize: 15, fontWeight: '800', lineHeight: 20, marginTop: 7 },
    lessonSub: { color: colors.sub, fontSize: 11, lineHeight: 16, marginTop: 3 },
    lessonTextLocked: { color: colors.muted },
    continueText: { color: colors.gold, fontSize: 12, fontWeight: '800', marginTop: 10 },
    pathNote: { flexDirection: 'row', gap: 12, marginTop: 20, padding: 16, borderRadius: radius.button, backgroundColor: colors.overlay },
    pathNoteIcon: { color: colors.gold, fontSize: 18 },
    pathNoteText: { flex: 1, color: colors.sub, fontSize: 11, lineHeight: 17 },
  })
}
