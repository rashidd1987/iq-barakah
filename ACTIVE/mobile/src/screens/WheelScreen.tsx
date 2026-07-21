import React, { useCallback, useMemo, useState } from 'react'
import { useFocusEffect } from '@react-navigation/native'
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import ScreenHeader from '../components/ScreenHeader'
import { useTheme } from '../context/ThemeContext'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { api } from '../utils/api'

// Ported 1:1 from the miniapp's SECTORS (ACTIVE/site/miniapp.html) — same 8 spheres,
// same Russian labels and colors, same 1-10 scale — but saved to the real
// wheel_records table instead of localStorage, so it survives reinstalls and is
// visible to curators.
const SECTORS = [
  { key: 'Вера (Иман)', color: '#2c5f2d' },
  { key: 'Намаз', color: '#3d7a3e' },
  { key: 'Семья', color: '#c9a84c' },
  { key: 'Здоровье', color: '#5b8fa8' },
  { key: 'Финансы', color: '#7b5ea7' },
  { key: 'Знание', color: '#e07b39' },
  { key: 'Ахляк (нрав)', color: '#d4547a' },
  { key: 'Умма', color: '#4a9e8c' },
]

const DEFAULT_SCORE = 5

export default function WheelScreen() {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const [scores, setScores] = useState<Record<string, number>>(() =>
    Object.fromEntries(SECTORS.map((s) => [s.key, DEFAULT_SCORE])),
  )
  const [lastSaved, setLastSaved] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError(false)
    api
      .getWheel()
      .then((res) => {
        if (res.scores) {
          setScores({ ...Object.fromEntries(SECTORS.map((s) => [s.key, DEFAULT_SCORE])), ...res.scores })
          setLastSaved(res.created_at)
        }
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  useFocusEffect(
    useCallback(() => {
      load()
    }, [load]),
  )

  const setScore = (key: string, val: number) => setScores((prev) => ({ ...prev, [key]: val }))

  const save = async () => {
    setSaving(true)
    try {
      await api.saveWheel(scores)
      setLastSaved(new Date().toISOString())
      Alert.alert('Сохранено', 'Оценка колеса баланса сохранена.')
    } catch {
      Alert.alert('Не удалось сохранить', 'Проверьте интернет-соединение и попробуйте снова.')
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
    return <ErrorState message="Не удалось загрузить колесо баланса" onRetry={load} />
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <ScreenHeader badge="Баланс" title="Колесо жизни" subtitle="Оцените каждую сферу от 1 до 10" />
      <View style={styles.body}>
      {lastSaved && (
        <Text style={styles.lastSaved}>Последняя оценка: {new Date(lastSaved).toLocaleDateString('ru-RU')}</Text>
      )}

      <View style={styles.card}>
        {SECTORS.map((s) => (
          <View key={s.key} style={styles.row}>
            <View style={styles.rowHead}>
              <View style={[styles.dot, { backgroundColor: s.color }]} />
              <Text style={styles.rowLabel}>{s.key}</Text>
              <Text style={[styles.rowValue, { color: s.color }]}>{scores[s.key]}</Text>
            </View>
            <View style={styles.scale}>
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <Pressable
                  key={n}
                  style={[
                    styles.scaleCell,
                    n <= scores[s.key] && { backgroundColor: s.color },
                  ]}
                  onPress={() => setScore(s.key, n)}
                />
              ))}
            </View>
          </View>
        ))}
      </View>

      <Pressable style={styles.saveButton} onPress={save} disabled={saving}>
        {saving ? <ActivityIndicator color={colors.onPrimary} /> : <Text style={styles.saveButtonText}>💾 Сохранить оценку</Text>}
      </Pressable>
      </View>
    </ScrollView>
  )
}

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  content: { paddingBottom: 32 },
  body: { padding: 16, marginTop: -16 },
  lastSaved: { fontSize: 12, color: colors.muted, marginBottom: 16, marginTop: 12 },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 16,
    marginTop: 12,
    marginBottom: 20,
    ...shadow.card,
  },
  row: { marginBottom: 18 },
  rowHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 8 },
  rowLabel: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.text },
  rowValue: { fontSize: 15, fontWeight: '800' },
  scale: { flexDirection: 'row', gap: 4 },
  scaleCell: { flex: 1, height: 14, borderRadius: 4, backgroundColor: colors.border },
  saveButton: {
    backgroundColor: colors.g2,
    paddingVertical: 14,
    borderRadius: radius.button,
    alignItems: 'center',
  },
  saveButtonText: { color: colors.onPrimary, fontSize: 16, fontWeight: '600' },
  })
}
