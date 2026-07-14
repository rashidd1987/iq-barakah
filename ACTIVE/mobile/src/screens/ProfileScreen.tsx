import * as Application from 'expo-application'
import React, { useEffect, useState } from 'react'
import { Alert, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native'
import ScreenHeader from '../components/ScreenHeader'
import { useAuth } from '../context/AuthContext'
import { globalWeekIndex } from '../data/weeks'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'
import { registerForPushNotifications } from '../utils/push'
import { lsGet, lsSet } from '../utils/storage'

const PUSH_ENABLED_KEY = 'push_enabled'

interface Achievement {
  icon: string
  label: string
  unlocked: boolean
}

export default function ProfileScreen() {
  const { logout, resetOnboarding } = useAuth()
  const [level, setLevel] = useState<string | null>(null)
  const [week, setWeek] = useState<number | null>(null)
  const [pushEnabled, setPushEnabled] = useState(false)
  const [togglingPush, setTogglingPush] = useState(false)
  const [muhasabaStreak, setMuhasabaStreak] = useState(0)
  const [completedSteps, setCompletedSteps] = useState(0)
  const [wheelDone, setWheelDone] = useState(false)

  useEffect(() => {
    api
      .participant()
      .then((p) => {
        setLevel(p.level)
        setWeek(p.week)
        setCompletedSteps(Math.max(0, globalWeekIndex(p.level, p.week) - 1))
      })
      .catch(() => {
        // level/week stay as "—" — logout and the push toggle below still work offline
      })

    api.muhasabaStreak().then((r) => setMuhasabaStreak(r.streak)).catch(() => {})
    api.getWheel().then((r) => setWheelDone(!!r.created_at)).catch(() => {})

    lsGet(PUSH_ENABLED_KEY, false).then(async (wasEnabled) => {
      if (!wasEnabled) return
      // Re-register on load: the Expo push token can rotate between app installs/updates,
      // so a stale token silently stops receiving pushes without this.
      const token = await registerForPushNotifications()
      setPushEnabled(!!token)
      if (!token) await lsSet(PUSH_ENABLED_KEY, false)
    })
  }, [])

  const achievements: Achievement[] = [
    { icon: '🔥', label: 'Стрик 7 дней', unlocked: muhasabaStreak >= 7 },
    { icon: '🔥', label: 'Стрик 14 дней', unlocked: muhasabaStreak >= 14 },
    { icon: '🔥', label: 'Стрик 30 дней', unlocked: muhasabaStreak >= 30 },
    { icon: '🔥', label: 'Стрик 40 дней', unlocked: muhasabaStreak >= 40 },
    { icon: '🌱', label: 'Первый шаг', unlocked: completedSteps >= 1 },
    { icon: '📚', label: '5 шагов пройдено', unlocked: completedSteps >= 5 },
    { icon: '🏆', label: 'ВАКТ завершён', unlocked: completedSteps >= 6 },
    { icon: '🎯', label: 'Колесо заполнено', unlocked: wheelDone },
  ]

  const handlePushToggle = async (value: boolean) => {
    setTogglingPush(true)
    try {
      if (value) {
        const token = await registerForPushNotifications()
        if (!token) {
          Alert.alert('Уведомления недоступны', 'Разрешите уведомления в настройках устройства.')
          setPushEnabled(false)
          await lsSet(PUSH_ENABLED_KEY, false)
          return
        }
      }
      setPushEnabled(value)
      await lsSet(PUSH_ENABLED_KEY, value)
    } finally {
      setTogglingPush(false)
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <ScreenHeader badge="Профиль" title="Твой путь" />
      <View style={styles.body}>
      <View style={[styles.card, styles.infoCard]}>
        <Text style={styles.infoLabel}>Уровень</Text>
        <Text style={styles.infoValue}>{level ?? '—'}</Text>
        <Text style={styles.infoLabel}>Шаг</Text>
        <Text style={styles.infoValue}>{week ?? '—'}</Text>
      </View>

      <View style={[styles.card, styles.row]}>
        <Text style={styles.rowLabel}>Push-напоминания (Фаджр, пятница)</Text>
        <Switch value={pushEnabled} onValueChange={handlePushToggle} disabled={togglingPush} />
      </View>

      <Text style={styles.sectionTitle}>Достижения</Text>
      <View style={styles.achievementsGrid}>
        {achievements.map((a, i) => (
          <View key={i} style={[styles.badge, !a.unlocked && styles.badgeLocked]}>
            <Text style={[styles.badgeIcon, !a.unlocked && styles.badgeIconLocked]}>{a.unlocked ? a.icon : '🔒'}</Text>
            <Text style={[styles.badgeLabel, !a.unlocked && styles.badgeLabelLocked]}>{a.label}</Text>
          </View>
        ))}
      </View>

      <Pressable style={styles.linkButton} onPress={resetOnboarding}>
        <Text style={styles.linkText}>Пройти диагностику заново</Text>
      </Pressable>

      <Pressable style={styles.logoutButton} onPress={logout}>
        <Text style={styles.logoutText}>Выйти</Text>
      </Pressable>

      <Text style={styles.buildTag}>build {Application.nativeBuildVersion ?? '?'}</Text>
      </View>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { paddingBottom: 32 },
  body: { padding: 16, marginTop: -16 },
  card: { backgroundColor: colors.card, borderRadius: radius.card, ...shadow.card },
  infoCard: { padding: 16, marginBottom: 12 },
  infoLabel: { fontSize: 12, color: colors.sub, marginTop: 8 },
  infoValue: { fontSize: 18, fontWeight: '700', color: colors.text },
  row: { padding: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  rowLabel: { fontSize: 14, color: colors.text, flex: 1, marginRight: 12 },
  sectionTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 8,
  },
  achievementsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 20 },
  badge: {
    width: '31%',
    backgroundColor: colors.gpale,
    borderRadius: radius.card,
    paddingVertical: 14,
    alignItems: 'center',
    ...shadow.card,
  },
  badgeLocked: { backgroundColor: colors.card, opacity: 0.6 },
  badgeIcon: { fontSize: 24, marginBottom: 6 },
  badgeIconLocked: { opacity: 0.5 },
  badgeLabel: { fontSize: 11, fontWeight: '600', color: colors.g2, textAlign: 'center', paddingHorizontal: 4 },
  badgeLabelLocked: { color: colors.muted },
  linkButton: { marginTop: 4, alignItems: 'center', padding: 12 },
  linkText: { color: colors.g2, fontSize: 14, fontWeight: '600' },
  logoutButton: { marginTop: 4, alignItems: 'center', padding: 12 },
  logoutText: { color: colors.muted, fontSize: 14 },
  buildTag: { textAlign: 'center', color: colors.border, fontSize: 11, marginTop: 8 },
})
