import * as Application from 'expo-application'
import React, { useEffect, useMemo, useState } from 'react'
import { Alert, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native'
import ScreenHeader from '../components/ScreenHeader'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { globalWeekIndex } from '../data/weeks'
import { makeShadow, radius, ThemeColors, ThemeMode, ThemePalette } from '../theme/colors'
import { api } from '../utils/api'
import { registerForPushNotifications } from '../utils/push'
import { lsGet, lsSet } from '../utils/storage'

const PUSH_ENABLED_KEY = 'push_enabled'

const PALETTE_OPTIONS: { value: ThemePalette; label: string; sub: string }[] = [
  { value: 'classic', label: 'Мужская', sub: 'Зелёный и золото' },
  { value: 'feminine', label: 'Женская', sub: 'Слива, роза и золото' },
]

const MODE_OPTIONS: { value: ThemeMode; label: string }[] = [
  { value: 'system', label: 'Системная' },
  { value: 'light', label: 'Светлая' },
  { value: 'dark', label: 'Тёмная' },
]

interface Achievement {
  icon: string
  label: string
  unlocked: boolean
}

export default function ProfileScreen() {
  const { logout, resetOnboarding } = useAuth()
  const { colors, palette, mode, setPalette, setMode } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
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
        <Switch
          value={pushEnabled}
          onValueChange={handlePushToggle}
          disabled={togglingPush}
          trackColor={{ false: colors.border, true: colors.gsoft }}
          thumbColor={pushEnabled ? colors.g2 : colors.muted}
        />
      </View>

      <Text style={styles.sectionTitle}>Оформление</Text>
      <View style={[styles.card, styles.themeCard]}>
        <Text style={styles.themeLabel}>Палитра</Text>
        <View style={styles.paletteGrid}>
          {PALETTE_OPTIONS.map((option) => {
            const selected = palette === option.value
            return (
              <Pressable
                key={option.value}
                accessibilityRole="radio"
                accessibilityState={{ checked: selected }}
                style={[styles.paletteOption, selected && styles.optionSelected]}
                onPress={() => setPalette(option.value)}
              >
                <View style={[styles.paletteSwatch, option.value === 'feminine' && styles.paletteSwatchFeminine]} />
                <Text style={[styles.optionLabel, selected && styles.optionLabelSelected]}>{option.label}</Text>
                <Text style={styles.optionSub}>{option.sub}</Text>
              </Pressable>
            )
          })}
        </View>

        <Text style={[styles.themeLabel, styles.modeLabel]}>Яркость</Text>
        <View style={styles.modeRow}>
          {MODE_OPTIONS.map((option) => {
            const selected = mode === option.value
            return (
              <Pressable
                key={option.value}
                accessibilityRole="radio"
                accessibilityState={{ checked: selected }}
                style={[styles.modeOption, selected && styles.optionSelected]}
                onPress={() => setMode(option.value)}
              >
                <Text style={[styles.modeText, selected && styles.optionLabelSelected]}>{option.label}</Text>
              </Pressable>
            )
          })}
        </View>
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

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { paddingBottom: 32 },
  body: { padding: 16, marginTop: -16 },
  card: { backgroundColor: colors.card, borderRadius: radius.card, ...shadow.card },
  infoCard: { padding: 16, marginBottom: 12 },
  infoLabel: { fontSize: 12, color: colors.sub, marginTop: 8 },
  infoValue: { fontSize: 18, fontWeight: '700', color: colors.text },
  row: { padding: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  rowLabel: { fontSize: 14, color: colors.text, flex: 1, marginRight: 12 },
  themeCard: { padding: 16, marginBottom: 20 },
  themeLabel: { color: colors.text, fontSize: 14, fontWeight: '700', marginBottom: 10 },
  modeLabel: { marginTop: 18 },
  paletteGrid: { flexDirection: 'row', gap: 10 },
  paletteOption: {
    flex: 1,
    minHeight: 92,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.button,
    padding: 12,
    backgroundColor: colors.cardRaised,
  },
  optionSelected: { borderColor: colors.gold, backgroundColor: colors.overlay },
  paletteSwatch: { width: 28, height: 10, borderRadius: 5, backgroundColor: '#2E6847', marginBottom: 8 },
  paletteSwatchFeminine: { backgroundColor: '#B97A85' },
  optionLabel: { color: colors.text, fontSize: 13, fontWeight: '700' },
  optionLabelSelected: { color: colors.g2 },
  optionSub: { color: colors.muted, fontSize: 11, marginTop: 3, lineHeight: 15 },
  modeRow: { flexDirection: 'row', gap: 8 },
  modeOption: {
    flex: 1,
    minHeight: 42,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.button,
    backgroundColor: colors.cardRaised,
  },
  modeText: { color: colors.sub, fontSize: 12, fontWeight: '600' },
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
}
