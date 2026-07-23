import { Ionicons } from '@expo/vector-icons'
import * as Application from 'expo-application'
import React, { useEffect, useMemo, useState } from 'react'
import { Alert, Platform, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native'
import ScreenHeader from '../components/ScreenHeader'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { globalWeekIndex, TOTAL_STEPS } from '../data/weeks'
import { makeShadow, radius, ThemeColors, ThemeMode, ThemePalette } from '../theme/colors'
import { api } from '../utils/api'
import { registerForPushNotifications } from '../utils/push'
import { getPwaInstallStatus, promptPwaInstall, PwaInstallStatus, subscribePwaInstallStatus } from '../utils/pwaInstall'
import { lsGet, lsSet } from '../utils/storage'

const PUSH_ENABLED_KEY = 'push_enabled'

const PALETTE_OPTIONS: { value: ThemePalette; label: string; sub: string; colors: [string, string] }[] = [
  { value: 'classic', label: 'Классическая', sub: 'Зелёный и золото', colors: ['#2E6847', '#C9A84C'] },
  { value: 'feminine', label: 'Женская', sub: 'Слива, роза и золото', colors: ['#7B5365', '#C6A15B'] },
]

const MODE_OPTIONS: { value: ThemeMode; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { value: 'system', label: 'Система', icon: 'phone-portrait-outline' },
  { value: 'light', label: 'Светлая', icon: 'sunny-outline' },
  { value: 'dark', label: 'Тёмная', icon: 'moon-outline' },
]

interface Achievement {
  icon: keyof typeof Ionicons.glyphMap
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
  const [pwaInstallStatus, setPwaInstallStatus] = useState<PwaInstallStatus>(getPwaInstallStatus())
  const [showInstallHelp, setShowInstallHelp] = useState(false)

  useEffect(() => {
    api.participant().then((p) => {
      setLevel(p.level)
      setWeek(p.week)
      setCompletedSteps(Math.max(0, globalWeekIndex(p.level, p.week) - 1))
    }).catch(() => {})
    api.muhasabaStreak().then((r) => setMuhasabaStreak(r.streak)).catch(() => {})
    api.getWheel().then((r) => setWheelDone(!!r.created_at)).catch(() => {})

    lsGet(PUSH_ENABLED_KEY, false).then(async (wasEnabled) => {
      if (!wasEnabled) return
      const token = await registerForPushNotifications()
      setPushEnabled(!!token)
      if (!token) await lsSet(PUSH_ENABLED_KEY, false)
    })
  }, [])

  useEffect(() => {
    if (Platform.OS !== 'web') return
    return subscribePwaInstallStatus(setPwaInstallStatus)
  }, [])

  const achievements: Achievement[] = [
    { icon: 'flame', label: 'Стрик 7 дней', unlocked: muhasabaStreak >= 7 },
    { icon: 'flame', label: 'Стрик 14 дней', unlocked: muhasabaStreak >= 14 },
    { icon: 'flame', label: 'Стрик 30 дней', unlocked: muhasabaStreak >= 30 },
    { icon: 'flame', label: 'Стрик 40 дней', unlocked: muhasabaStreak >= 40 },
    { icon: 'leaf', label: 'Первый шаг', unlocked: completedSteps >= 1 },
    { icon: 'book', label: '5 шагов пройдено', unlocked: completedSteps >= 5 },
    { icon: 'trophy', label: 'ВАКТ завершён', unlocked: completedSteps >= 6 },
    { icon: 'analytics', label: 'Колесо заполнено', unlocked: wheelDone },
  ]
  const unlockedCount = achievements.filter((item) => item.unlocked).length
  const progress = Math.min(100, Math.round((completedSteps / TOTAL_STEPS) * 100))

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

  const handlePwaInstall = async () => {
    if (pwaInstallStatus === 'installed') return
    if (pwaInstallStatus === 'installable') {
      const installed = await promptPwaInstall()
      if (installed) setShowInstallHelp(false)
      return
    }
    setShowInstallHelp(true)
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <ScreenHeader badge="Профиль" title="Твой путь" />
      <View style={styles.body}>
        <View style={[styles.card, styles.heroCard]}>
          <View style={styles.avatar}><Ionicons name="person" size={30} color={colors.onPrimary} /></View>
          <View style={styles.heroCopy}>
            <Text style={styles.heroEyebrow}>IQ BARAKAH</Text>
            <Text style={styles.heroTitle}>Путь к постоянству</Text>
            <Text style={styles.heroMeta}>Уровень {level ?? '—'} · шаг {week ?? '—'}</Text>
          </View>
          <View style={styles.percentPill}><Text style={styles.percentText}>{progress}%</Text></View>
          <View style={styles.progressTrack}><View style={[styles.progressFill, { width: `${progress}%` }]} /></View>
          <View style={styles.statsRow}>
            <Stat value={`${completedSteps}/${TOTAL_STEPS}`} label="Шагов" colors={colors} />
            <View style={styles.statDivider} />
            <Stat value={`${muhasabaStreak}`} label="Дней подряд" colors={colors} />
            <View style={styles.statDivider} />
            <Stat value={`${unlockedCount}/${achievements.length}`} label="Наград" colors={colors} />
          </View>
        </View>

        <Text style={styles.sectionTitle}>Оформление</Text>
        <View style={[styles.card, styles.themeCard]}>
          <Text style={styles.cardTitle}>Палитра</Text>
          <View style={styles.paletteGrid}>
            {PALETTE_OPTIONS.map((option) => {
              const selected = palette === option.value
              return (
                <Pressable key={option.value} accessibilityRole="radio" accessibilityState={{ checked: selected }} style={[styles.paletteOption, selected && styles.optionSelected]} onPress={() => setPalette(option.value)}>
                  <View style={styles.swatchRow}><View style={[styles.swatch, { backgroundColor: option.colors[0] }]} /><View style={[styles.swatch, styles.swatchOverlap, { backgroundColor: option.colors[1] }]} />{selected && <Ionicons name="checkmark-circle" size={20} color={colors.g2} style={styles.checkmark} />}</View>
                  <Text style={[styles.optionLabel, selected && styles.optionLabelSelected]}>{option.label}</Text>
                  <Text style={styles.optionSub}>{option.sub}</Text>
                </Pressable>
              )
            })}
          </View>
          <Text style={[styles.cardTitle, styles.modeTitle]}>Яркость</Text>
          <View style={styles.modeRow}>
            {MODE_OPTIONS.map((option) => {
              const selected = mode === option.value
              return (
                <Pressable key={option.value} accessibilityRole="radio" accessibilityState={{ checked: selected }} style={[styles.modeOption, selected && styles.modeSelected]} onPress={() => setMode(option.value)}>
                  <Ionicons name={option.icon} size={17} color={selected ? colors.g2 : colors.muted} />
                  <Text style={[styles.modeText, selected && styles.optionLabelSelected]}>{option.label}</Text>
                </Pressable>
              )
            })}
          </View>
        </View>

        <Text style={styles.sectionTitle}>Настройки</Text>
        <View style={[styles.card, styles.settingsCard]}>
          {Platform.OS === 'web' && (
            <>
              <Pressable style={styles.settingRow} onPress={handlePwaInstall} disabled={pwaInstallStatus === 'installed'}>
                <View style={styles.settingIcon}><Ionicons name={pwaInstallStatus === 'installed' ? 'checkmark-circle-outline' : 'phone-portrait-outline'} size={21} color={colors.g2} /></View>
                <View style={styles.settingCopy}>
                  <Text style={styles.settingTitle}>{pwaInstallStatus === 'installed' ? 'Приложение установлено' : 'Установить на телефон'}</Text>
                  <Text style={styles.settingSub}>{pwaInstallStatus === 'installed' ? 'IQ Barakah уже на главном экране' : 'Добавить отдельную иконку IQ Barakah'}</Text>
                </View>
                {pwaInstallStatus !== 'installed' && <Ionicons name="chevron-forward" size={19} color={colors.muted} />}
              </Pressable>
              {showInstallHelp && pwaInstallStatus !== 'installed' && (
                <View style={styles.installHelp}>
                  <Ionicons name="information-circle-outline" size={20} color={colors.gold} />
                  <View style={styles.installHelpCopy}>
                    <Text style={styles.installHelpTitle}>{pwaInstallStatus === 'ios' ? 'Установка на iPhone' : 'Установка через браузер'}</Text>
                    <Text style={styles.installHelpText}>{pwaInstallStatus === 'ios' ? 'Откройте эту страницу в Safari, нажмите «Поделиться» и выберите «На экран Домой».' : 'Откройте меню браузера и выберите «Установить приложение» или «Добавить на главный экран».'}</Text>
                  </View>
                </View>
              )}
              <View style={styles.separator} />
            </>
          )}
          <View style={styles.settingRow}>
            <View style={styles.settingIcon}><Ionicons name="notifications-outline" size={21} color={colors.g2} /></View>
            <View style={styles.settingCopy}><Text style={styles.settingTitle}>Напоминания</Text><Text style={styles.settingSub}>Фаджр и пятница</Text></View>
            <Switch value={pushEnabled} onValueChange={handlePushToggle} disabled={togglingPush} trackColor={{ false: colors.border, true: colors.gsoft }} thumbColor={pushEnabled ? colors.g2 : colors.muted} />
          </View>
          <View style={styles.separator} />
          <Pressable style={styles.settingRow} onPress={resetOnboarding}>
            <View style={styles.settingIcon}><Ionicons name="compass-outline" size={21} color={colors.g2} /></View>
            <View style={styles.settingCopy}><Text style={styles.settingTitle}>Повторить диагностику</Text><Text style={styles.settingSub}>Обновить точку старта</Text></View>
            <Ionicons name="chevron-forward" size={19} color={colors.muted} />
          </Pressable>
        </View>

        <Text style={styles.sectionTitle}>Достижения</Text>
        <View style={styles.achievementsGrid}>
          {achievements.map((achievement) => (
            <View key={achievement.label} style={[styles.achievement, !achievement.unlocked && styles.achievementLocked]}>
              <View style={[styles.achievementIcon, achievement.unlocked && styles.achievementIconUnlocked]}>
                <Ionicons name={achievement.unlocked ? achievement.icon : 'lock-closed-outline'} size={21} color={achievement.unlocked ? colors.gold : colors.muted} />
              </View>
              <Text style={[styles.achievementLabel, !achievement.unlocked && styles.achievementLabelLocked]}>{achievement.label}</Text>
            </View>
          ))}
        </View>

        <Pressable style={styles.logoutButton} onPress={logout}><Ionicons name="log-out-outline" size={19} color={colors.danger} /><Text style={styles.logoutText}>Выйти из аккаунта</Text></Pressable>
        <Text style={styles.buildTag}>IQ Barakah · build {Application.nativeBuildVersion ?? '?'}</Text>
      </View>
    </ScrollView>
  )
}

function Stat({ value, label, colors }: { value: string; label: string; colors: ThemeColors }) {
  return <View style={statStyles.item}><Text style={[statStyles.value, { color: colors.text }]}>{value}</Text><Text style={[statStyles.label, { color: colors.muted }]}>{label}</Text></View>
}

const statStyles = StyleSheet.create({ item: { flex: 1, alignItems: 'center' }, value: { fontSize: 17, fontWeight: '800' }, label: { fontSize: 10, fontWeight: '600', marginTop: 2 } })

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg }, content: { paddingBottom: 34 }, body: { padding: 16, marginTop: -16 },
    card: { backgroundColor: colors.card, borderRadius: radius.card, ...shadow.card },
    heroCard: { padding: 18, marginBottom: 24, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center' },
    avatar: { width: 54, height: 54, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.g2 },
    heroCopy: { flex: 1, paddingHorizontal: 13 }, heroEyebrow: { color: colors.gold, fontSize: 10, fontWeight: '800', letterSpacing: 1.2 },
    heroTitle: { color: colors.text, fontSize: 17, lineHeight: 22, fontWeight: '800', marginTop: 3 }, heroMeta: { color: colors.sub, fontSize: 12, marginTop: 4 },
    percentPill: { backgroundColor: colors.goldpale, borderRadius: 12, paddingHorizontal: 9, paddingVertical: 5 }, percentText: { color: colors.g1, fontSize: 12, fontWeight: '800' },
    progressTrack: { width: '100%', height: 7, borderRadius: 4, backgroundColor: colors.border, overflow: 'hidden', marginTop: 18 }, progressFill: { height: '100%', borderRadius: 4, backgroundColor: colors.gold },
    statsRow: { width: '100%', flexDirection: 'row', alignItems: 'center', marginTop: 18 }, statDivider: { width: 1, height: 27, backgroundColor: colors.border },
    sectionTitle: { fontSize: 11, fontWeight: '800', color: colors.muted, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 9, marginLeft: 2 },
    themeCard: { padding: 16, marginBottom: 24 }, cardTitle: { color: colors.text, fontSize: 14, fontWeight: '700', marginBottom: 10 }, paletteGrid: { flexDirection: 'row', gap: 10 },
    paletteOption: { flex: 1, minHeight: 105, borderWidth: 1, borderColor: colors.border, borderRadius: radius.button, padding: 12, backgroundColor: colors.cardRaised }, optionSelected: { borderColor: colors.gold, backgroundColor: colors.overlay },
    swatchRow: { flexDirection: 'row', alignItems: 'center', height: 26, marginBottom: 8 }, swatch: { width: 27, height: 27, borderRadius: 14, borderWidth: 2, borderColor: colors.cardRaised }, swatchOverlap: { marginLeft: -8 }, checkmark: { marginLeft: 'auto' },
    optionLabel: { color: colors.text, fontSize: 13, fontWeight: '700' }, optionLabelSelected: { color: colors.g2 }, optionSub: { color: colors.muted, fontSize: 10, lineHeight: 14, marginTop: 3 },
    modeTitle: { marginTop: 18 }, modeRow: { flexDirection: 'row', gap: 7 }, modeOption: { flex: 1, minHeight: 46, alignItems: 'center', justifyContent: 'center', gap: 3, borderRadius: 12, backgroundColor: colors.cardRaised, borderWidth: 1, borderColor: colors.border }, modeSelected: { borderColor: colors.gold, backgroundColor: colors.overlay }, modeText: { color: colors.muted, fontSize: 10, fontWeight: '700' },
    settingsCard: { paddingHorizontal: 16, marginBottom: 24 }, settingRow: { minHeight: 72, flexDirection: 'row', alignItems: 'center' }, settingIcon: { width: 40, height: 40, borderRadius: 13, backgroundColor: colors.overlay, alignItems: 'center', justifyContent: 'center', marginRight: 12 }, settingCopy: { flex: 1 }, settingTitle: { color: colors.text, fontSize: 14, fontWeight: '700' }, settingSub: { color: colors.muted, fontSize: 11, marginTop: 3 }, separator: { height: 1, backgroundColor: colors.border, marginLeft: 52 },
    installHelp: { flexDirection: 'row', gap: 9, padding: 12, marginBottom: 12, borderRadius: 13, backgroundColor: colors.goldpale }, installHelpCopy: { flex: 1 }, installHelpTitle: { color: colors.text, fontSize: 12, fontWeight: '800' }, installHelpText: { color: colors.sub, fontSize: 11, lineHeight: 16, marginTop: 3 },
    achievementsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 20 }, achievement: { width: '48%', minHeight: 74, padding: 11, flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: radius.button, ...shadow.card }, achievementLocked: { elevation: 0, shadowOpacity: 0, borderWidth: 1, borderColor: colors.border }, achievementIcon: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.overlay, marginRight: 9 }, achievementIconUnlocked: { backgroundColor: colors.goldpale }, achievementLabel: { flex: 1, color: colors.text, fontSize: 11, lineHeight: 15, fontWeight: '700' }, achievementLabelLocked: { color: colors.muted },
    logoutButton: { minHeight: 52, borderRadius: radius.button, borderWidth: 1, borderColor: colors.dangerSoft, backgroundColor: colors.card, flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' }, logoutText: { color: colors.danger, fontSize: 14, fontWeight: '700' }, buildTag: { textAlign: 'center', color: colors.muted, fontSize: 10, marginTop: 14 },
  })
}
