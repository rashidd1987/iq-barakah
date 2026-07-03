import React, { useCallback, useState } from 'react'
import { useFocusEffect } from '@react-navigation/native'
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import { DAILY, NAMAZ, WEEKLY } from '../data/habits'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'
import { todayKey } from '../utils/storage'

type Habits = { namaz: Record<string, boolean>; daily: Record<string, boolean>; weekly: Record<string, boolean> }

const EMPTY_HABITS: Habits = { namaz: {}, daily: {}, weekly: {} }

export default function TrackerScreen() {
  const [habits, setHabits] = useState<Habits>(EMPTY_HABITS)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [saving, setSaving] = useState(false)
  const date = todayKey()

  const load = useCallback(async () => {
    setLoading(true)
    setError(false)
    try {
      const records = await api.tracker(1)
      const today = records.find((r: any) => r.date === date) as { habits?: Partial<Habits> } | undefined
      setHabits({ ...EMPTY_HABITS, ...(today?.habits ?? {}) })
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [date])

  useFocusEffect(
    useCallback(() => {
      load()
    }, [load]),
  )

  const toggle = async (bucket: keyof Habits, id: string) => {
    const previous = habits
    const next: Habits = { ...habits, [bucket]: { ...habits[bucket], [id]: !habits[bucket][id] } }
    setHabits(next)
    setSaving(true)
    try {
      await api.saveTracker(date, next)
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
    return <ErrorState message="Не удалось загрузить трекер" onRetry={load} />
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Section title="🕌 Намаз" bucket="namaz" items={NAMAZ} habits={habits} onToggle={toggle} />
      <Section title="☀️ Каждый день" bucket="daily" items={DAILY} habits={habits} onToggle={toggle} />
      <Section title="📅 На неделю" bucket="weekly" items={WEEKLY} habits={habits} onToggle={toggle} />
      {saving && <Text style={styles.savingHint}>Сохранение…</Text>}
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
  content: { padding: 16, paddingBottom: 32 },
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
  check: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkDone: { backgroundColor: colors.g2, borderColor: colors.g2 },
  checkMark: { color: '#fff', fontSize: 13, fontWeight: '700' },
  savingHint: { textAlign: 'center', color: colors.muted, fontSize: 12 },
})
