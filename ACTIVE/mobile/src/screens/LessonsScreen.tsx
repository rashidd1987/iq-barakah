import { NativeStackScreenProps } from '@react-navigation/native-stack'
import React, { useCallback, useState } from 'react'
import { useFocusEffect } from '@react-navigation/native'
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native'
import { LessonsStackParamList } from '../navigation/types'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'

const LEVEL_WEEKS: Record<string, number> = { А: 6, Б: 8, В: 8, Г: 8 }

type Props = NativeStackScreenProps<LessonsStackParamList, 'LessonsList'>

export default function LessonsScreen({ navigation }: Props) {
  const [level, setLevel] = useState<string | null>(null)
  const [currentWeek, setCurrentWeek] = useState(1)

  useFocusEffect(
    useCallback(() => {
      api.participant().then((p) => {
        setLevel(p.level)
        setCurrentWeek(p.week)
      })
    }, []),
  )

  const totalWeeks = level ? LEVEL_WEEKS[level] ?? 8 : 0
  const weeks = Array.from({ length: totalWeeks }, (_, i) => i + 1)

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.content}
      data={weeks}
      keyExtractor={(w) => String(w)}
      renderItem={({ item: weekNum }) => {
        const locked = weekNum > currentWeek
        return (
          <Pressable
            style={[styles.card, locked && styles.cardLocked]}
            disabled={locked || !level}
            onPress={() => level && navigation.navigate('LessonDetail', { level, week: weekNum })}
          >
            <Text style={styles.weekLabel}>{locked ? '🔒' : '📖'} Неделя {weekNum}</Text>
            {weekNum === currentWeek && <Text style={styles.currentBadge}>Текущая</Text>}
          </Pressable>
        )
      }}
    />
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, gap: 10 },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    ...shadow.card,
  },
  cardLocked: { opacity: 0.5 },
  weekLabel: { fontSize: 16, fontWeight: '600', color: colors.text },
  currentBadge: {
    color: colors.g2,
    backgroundColor: colors.gpale,
    fontSize: 12,
    fontWeight: '600',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
})
