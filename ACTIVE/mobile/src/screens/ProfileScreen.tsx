import { Ionicons } from '@expo/vector-icons'
import * as Application from 'expo-application'
import React, { useEffect, useMemo, useState } from 'react'
import { Alert, Platform, Pressable, ScrollView, Share, StyleSheet, Switch, Text, TextInput, View } from 'react-native'
import ScreenHeader from '../components/ScreenHeader'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { globalWeekIndex, TOTAL_STEPS } from '../data/weeks'
import { makeShadow, radius, ThemeColors, ThemeMode, ThemePalette } from '../theme/colors'
import { api, MobileProfile, setToken } from '../utils/api'
import { registerForPushNotifications } from '../utils/push'
import { getPwaInstallGuide, getPwaInstallStatus, promptPwaInstall, PwaInstallStatus, subscribePwaInstallStatus } from '../utils/pwaInstall'
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
  const [profile, setProfile] = useState<MobileProfile | null>(null)
  const [profileError, setProfileError] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showDeleteAccount, setShowDeleteAccount] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deletingAccount, setDeletingAccount] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [emailChallengeId, setEmailChallengeId] = useState<string | null>(null)
  const [emailCode, setEmailCode] = useState('')
  const [emailLinking, setEmailLinking] = useState(false)
  const [emailLinkMessage, setEmailLinkMessage] = useState<string | null>(null)
  const [emailLoginEnabled, setEmailLoginEnabled] = useState(false)

  useEffect(() => {
    api.profile().then((data) => {
      setProfile(data)
      setName(data.personal.name)
      setEmail(data.personal.email ?? '')
      setEmailLoginEnabled(data.personal.email_login_enabled)
      setPhone(data.personal.phone ?? '')
      setLevel(data.program.level)
      setWeek(data.program.week)
      setCompletedSteps(data.program.weeks_completed)
    }).catch(() => setProfileError(true))
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
    { icon: 'trophy', label: 'Старт завершён', unlocked: completedSteps >= 6 },
    { icon: 'analytics', label: 'Колесо заполнено', unlocked: wheelDone },
  ]
  const unlockedCount = achievements.filter((item) => item.unlocked).length
  const progress = Math.min(100, Math.round((completedSteps / TOTAL_STEPS) * 100))
  const installGuide = useMemo(() => getPwaInstallGuide(pwaInstallStatus), [pwaInstallStatus])

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
      setShowInstallHelp(!installed)
      return
    }
    setShowInstallHelp(true)
  }

  const handleSaveProfile = async () => {
    if (name.trim().length < 2) {
      Alert.alert('Проверьте ФИО', 'Укажите имя длиной не менее двух символов.')
      return
    }
    setSaving(true)
    try {
      await api.updateProfile({
        name: name.trim(),
        email: email.trim() || null,
        phone: phone.trim() || null,
      })
      setProfile((current) => current ? {
        ...current,
        personal: {
          ...current.personal,
          name: name.trim(),
          email: email.trim() || null,
          phone: phone.trim() || null,
        },
      } : current)
      setEditing(false)
      setEmailChallengeId(null)
      setEmailCode('')
      setEmailLinkMessage(null)
      setEmailLoginEnabled(false)
      Alert.alert('Сохранено', 'Данные профиля обновлены.')
    } catch {
      Alert.alert('Не удалось сохранить', 'Проверьте email и подключение к интернету.')
    } finally {
      setSaving(false)
    }
  }

  const handleEmailLinkRequest = async () => {
    const value = email.trim().toLowerCase()
    if (!value || !value.includes('@')) {
      Alert.alert('Сначала добавьте email', 'Укажите email в профиле и сохраните изменения.')
      return
    }
    setEmailLinking(true)
    setEmailLinkMessage(null)
    try {
      const result = await api.requestEmailOtp(value, name.trim())
      setEmailChallengeId(result.challenge_id)
      setEmailCode('')
      setEmailLinkMessage('Код отправлен на почту. Он действует 10 минут.')
    } catch {
      setEmailLinkMessage('Не удалось отправить код. Проверьте адрес и попробуйте позже.')
    } finally {
      setEmailLinking(false)
    }
  }

  const handleEmailLinkVerify = async () => {
    if (!emailChallengeId || !/^\d{6}$/.test(emailCode.trim())) {
      setEmailLinkMessage('Введите шестизначный код из письма.')
      return
    }
    setEmailLinking(true)
    setEmailLinkMessage(null)
    try {
      const result = await api.verifyEmailOtp(emailChallengeId, emailCode.trim())
      await setToken(result.access_token)
      setEmailChallengeId(null)
      setEmailCode('')
      setEmailLoginEnabled(true)
      setEmailLinkMessage('Email подтверждён. Теперь по нему можно входить без Telegram.')
    } catch {
      setEmailLinkMessage('Код неверный или устарел. Запросите новый.')
    } finally {
      setEmailLinking(false)
    }
  }

  const handleShareReferral = async () => {
    if (!profile?.referral.link) return
    await Share.share({
      title: 'IQ Barakah',
      message: `Присоединяйтесь к программе IQ Barakah: ${profile.referral.link}`,
      url: profile.referral.link,
    })
  }

  const handleDeleteAccount = async () => {
    if (deleteConfirmation.trim() !== 'УДАЛИТЬ') {
      Alert.alert('Нужно подтверждение', 'Введите слово УДАЛИТЬ без кавычек.')
      return
    }
    setDeletingAccount(true)
    try {
      await api.deleteAccount(deleteConfirmation)
      await logout()
      Alert.alert('Аккаунт удалён', 'Личные данные и прогресс удалены. Финансовые записи сохранены только в обезличенном виде.')
    } catch {
      Alert.alert('Не удалось удалить аккаунт', 'Данные не изменены. Проверьте подключение и попробуйте снова.')
    } finally {
      setDeletingAccount(false)
    }
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

        <Text style={styles.sectionTitle}>Личные данные</Text>
        <View style={[styles.card, styles.profileCard]}>
          <View style={styles.cardHeading}>
            <View>
              <Text style={styles.cardTitleNoMargin}>Профиль ученика</Text>
              <Text style={styles.cardHint}>Вход защищён через Telegram</Text>
            </View>
            <Pressable style={styles.smallAction} onPress={() => setEditing((value) => !value)}>
              <Ionicons name={editing ? 'close' : 'create-outline'} size={17} color={colors.g2} />
              <Text style={styles.smallActionText}>{editing ? 'Отмена' : 'Изменить'}</Text>
            </Pressable>
          </View>
          {profileError && <Text style={styles.inlineError}>Не удалось загрузить данные. Потяните экран для повторной попытки.</Text>}
          <ProfileField label="ФИО" value={name} editing={editing} onChangeText={setName} colors={colors} />
          <ProfileField label="Email" value={email} editing={editing} onChangeText={setEmail} keyboardType="email-address" colors={colors} placeholder="Добавить email" />
          {!editing && email.trim() && !emailLoginEnabled ? (
            <View style={styles.emailLinkPanel}>
              <View style={styles.emailLinkHeading}>
                <Ionicons name="mail-outline" size={18} color={colors.g2} />
                <View style={styles.authCopy}>
                  <Text style={styles.fieldLabel}>ВХОД ПО EMAIL</Text>
                  <Text style={styles.emailLinkHint}>Подтвердите адрес кодом, чтобы входить без Telegram.</Text>
                </View>
              </View>
              {emailChallengeId ? (
                <TextInput
                  value={emailCode}
                  onChangeText={(value) => setEmailCode(value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="Код из письма"
                  placeholderTextColor={colors.muted}
                  keyboardType="number-pad"
                  autoComplete="one-time-code"
                  maxLength={6}
                  editable={!emailLinking}
                  style={styles.emailCodeInput}
                />
              ) : null}
              <Pressable
                style={[styles.emailLinkButton, emailLinking && styles.buttonDisabled]}
                onPress={emailChallengeId ? handleEmailLinkVerify : handleEmailLinkRequest}
                disabled={emailLinking}
              >
                <Text style={styles.emailLinkButtonText}>
                  {emailLinking ? 'Проверяем…' : emailChallengeId ? 'Подтвердить код' : 'Подтвердить email'}
                </Text>
              </Pressable>
              {emailChallengeId ? (
                <Pressable onPress={handleEmailLinkRequest} disabled={emailLinking}>
                  <Text style={styles.emailLinkRetry}>Отправить новый код</Text>
                </Pressable>
              ) : null}
              {emailLinkMessage ? <Text style={styles.emailLinkMessage}>{emailLinkMessage}</Text> : null}
            </View>
          ) : null}
          {!editing && email.trim() && emailLoginEnabled ? (
            <View style={styles.emailLinkedRow}>
              <Ionicons name="checkmark-circle" size={18} color={colors.g2} />
              <Text style={styles.emailLinkedText}>Вход по email включён</Text>
            </View>
          ) : null}
          <ProfileField label="Телефон" value={phone} editing={editing} onChangeText={setPhone} keyboardType="phone-pad" colors={colors} placeholder="Добавить телефон" />
          <View style={styles.authRow}>
            <Ionicons name="paper-plane-outline" size={18} color={colors.g2} />
            <View style={styles.authCopy}>
              <Text style={styles.fieldLabel}>СПОСОБ ВХОДА</Text>
              <Text style={styles.fieldValue}>Telegram{profile?.personal.username ? ` · @${profile.personal.username}` : ''}</Text>
            </View>
            <Ionicons name="shield-checkmark" size={20} color={colors.completed} />
          </View>
          {editing && (
            <Pressable style={[styles.primaryButton, saving && styles.buttonDisabled]} onPress={handleSaveProfile} disabled={saving}>
              <Text style={styles.primaryButtonText}>{saving ? 'Сохраняем…' : 'Сохранить изменения'}</Text>
            </Pressable>
          )}
        </View>

        <Text style={styles.sectionTitle}>Результаты за всё время</Text>
        <View style={[styles.card, styles.journeyCard]}>
          <View style={styles.metricGrid}>
            <Metric icon="checkmark-done" value={profile?.program.weeks_completed ?? completedSteps} label="шагов пройдено" colors={colors} />
            <Metric icon="list" value={profile?.program.tasks_completed ?? 0} label="заданий выполнено" colors={colors} />
            <Metric icon="calendar" value={profile?.program.tracker_days ?? 0} label="дней трекера" colors={colors} />
            <Metric icon="moon" value={profile?.program.muhasaba_count ?? 0} label="мухасаба" colors={colors} />
          </View>
          <View style={styles.journeyFooter}>
            <Ionicons name="time-outline" size={18} color={colors.gold} />
            <Text style={styles.journeyFooterText}>
              {profile?.program.first_step_at
                ? `Первый шаг: ${new Date(profile.program.first_step_at).toLocaleDateString('ru-RU')}`
                : 'Первый завершённый шаг появится здесь'}
            </Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Приглашённые и Баракаты</Text>
        <View style={[styles.card, styles.referralCard]}>
          <View style={styles.referralTop}>
            <View>
              <Text style={styles.cardTitleNoMargin}>Твоя реферальная ссылка</Text>
              <Text numberOfLines={1} style={styles.referralLink}>{profile?.referral.link ?? 'Загрузка…'}</Text>
            </View>
            <Pressable style={styles.shareButton} onPress={handleShareReferral} disabled={!profile}>
              <Ionicons name="share-social-outline" size={20} color={colors.onPrimary} />
            </Pressable>
          </View>
          <View style={styles.referralStats}>
            <Stat value={`${profile?.referral.invited_count ?? 0}`} label="Приглашено" colors={colors} />
            <View style={styles.statDivider} />
            <Stat value={`${profile?.referral.active_count ?? 0}`} label="Учатся" colors={colors} />
            <View style={styles.statDivider} />
            <Stat value={`${profile?.referral.paid_count ?? 0}`} label="Оплатили" colors={colors} />
            <View style={styles.statDivider} />
            <Stat value={`${profile?.referral.barakah_balance ?? 0}`} label="Баракатов" colors={colors} />
          </View>
          {!!profile?.referral.people.length && (
            <View style={styles.peopleList}>
              {profile.referral.people.slice(0, 5).map((person, index) => (
                <View key={`${person.first_name}-${index}`} style={styles.personRow}>
                  <View style={styles.personAvatar}><Text style={styles.personAvatarText}>{person.first_name.slice(0, 1).toUpperCase()}</Text></View>
                  <View style={styles.personCopy}>
                    <Text style={styles.personName}>{person.first_name}</Text>
                    <Text style={styles.personMeta}>
                      {person.graduated ? 'Завершил программу' : person.level ? `Уровень ${person.level} · шаг ${person.week}` : 'Зарегистрирован'}
                    </Text>
                  </View>
                  <Text style={styles.personSteps}>{person.completed_steps} шаг.</Text>
                </View>
              ))}
            </View>
          )}
        </View>

        <Text style={styles.sectionTitle}>Вклад в благотворительность</Text>
        <View style={[styles.card, styles.charityCard]}>
          <View style={styles.charityIcon}><Ionicons name="heart" size={24} color={colors.gold} /></View>
          <View style={styles.charityLead}>
            <Text style={styles.charityAmount}>{profile?.charity.own_reserved ?? 0} ₽</Text>
            <Text style={styles.charityLabel}>рассчитано из твоих оплат</Text>
          </View>
          <View style={styles.charityDivider} />
          <View style={styles.charityRow}><Text style={styles.charityRowLabel}>Через приглашённых</Text><Text style={styles.charityRowValue}>{profile?.charity.referral_reserved ?? 0} ₽</Text></View>
          <View style={styles.charityRow}><Text style={styles.charityRowLabel}>Общий резерв программы</Text><Text style={styles.charityRowValue}>{profile?.charity.community_reserved ?? 0} ₽</Text></View>
          <Text style={styles.charityNote}>Расчёт: 20% от подтверждённых оплат. Фактически перечисленные средства появятся после подключения подтверждённого реестра переводов.</Text>
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
          {Platform.OS === 'web' && pwaInstallStatus !== 'installed' && (
            <>
              <Pressable style={styles.settingRow} onPress={handlePwaInstall}>
                <View style={styles.settingIcon}><Ionicons name="phone-portrait-outline" size={21} color={colors.g2} /></View>
                <View style={styles.settingCopy}>
                  <Text style={styles.settingTitle}>Установить на телефон</Text>
                  <Text style={styles.settingSub}>{pwaInstallStatus === 'installable' ? 'Установить IQ Barakah одним нажатием' : 'Добавить отдельную иконку IQ Barakah'}</Text>
                </View>
                <Ionicons name="chevron-forward" size={19} color={colors.muted} />
              </Pressable>
              {showInstallHelp && (
                <View style={styles.installHelp}>
                  <Ionicons name="information-circle-outline" size={20} color={colors.gold} />
                  <View style={styles.installHelpCopy}>
                    <Text style={styles.installHelpTitle}>{installGuide.title}</Text>
                    {installGuide.steps.map((step, index) => (
                      <View key={step} style={styles.installStep}>
                        <View style={styles.installStepNumber}><Text style={styles.installStepNumberText}>{index + 1}</Text></View>
                        <Text style={styles.installHelpText}>{step}</Text>
                      </View>
                    ))}
                    <Text style={styles.installHelpNote}>{installGuide.note}</Text>
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
        <Pressable
          style={styles.deleteAccountButton}
          onPress={() => {
            setShowDeleteAccount((value) => !value)
            setDeleteConfirmation('')
          }}
          disabled={deletingAccount}
        >
          <Ionicons name="trash-outline" size={18} color={colors.danger} />
          <Text style={styles.deleteAccountText}>{showDeleteAccount ? 'Отменить удаление' : 'Удалить аккаунт'}</Text>
        </Pressable>
        {showDeleteAccount && (
          <View style={styles.deleteAccountPanel}>
            <Text style={styles.deleteAccountTitle}>Удалить аккаунт безвозвратно?</Text>
            <Text style={styles.deleteAccountHint}>
              Будут удалены профиль, прогресс, трекер, мухасаба, колесо и push-токен.
              Подтверждённые платежи останутся только как обезличенные финансовые записи.
            </Text>
            <TextInput
              value={deleteConfirmation}
              onChangeText={setDeleteConfirmation}
              autoCapitalize="characters"
              autoCorrect={false}
              placeholder="Введите УДАЛИТЬ"
              placeholderTextColor={colors.muted}
              editable={!deletingAccount}
              style={styles.deleteAccountInput}
            />
            <Pressable
              style={[
                styles.deleteAccountConfirm,
                (deleteConfirmation.trim() !== 'УДАЛИТЬ' || deletingAccount) && styles.buttonDisabled,
              ]}
              onPress={handleDeleteAccount}
              disabled={deleteConfirmation.trim() !== 'УДАЛИТЬ' || deletingAccount}
            >
              <Text style={styles.deleteAccountConfirmText}>
                {deletingAccount ? 'Удаляем…' : 'Удалить навсегда'}
              </Text>
            </Pressable>
          </View>
        )}
        {Platform.OS !== 'web' && Application.nativeBuildVersion ? (
          <Text style={styles.buildTag}>IQ Barakah · build {Application.nativeBuildVersion}</Text>
        ) : null}
      </View>
    </ScrollView>
  )
}

function Stat({ value, label, colors }: { value: string; label: string; colors: ThemeColors }) {
  return <View style={statStyles.item}><Text style={[statStyles.value, { color: colors.text }]}>{value}</Text><Text style={[statStyles.label, { color: colors.muted }]}>{label}</Text></View>
}

function ProfileField({
  label, value, editing, onChangeText, colors, placeholder, keyboardType = 'default',
}: {
  label: string
  value: string
  editing: boolean
  onChangeText: (value: string) => void
  colors: ThemeColors
  placeholder?: string
  keyboardType?: 'default' | 'email-address' | 'phone-pad'
}) {
  return (
    <View style={[profileFieldStyles.row, { borderBottomColor: colors.border }]}>
      <Text style={[profileFieldStyles.label, { color: colors.muted }]}>{label.toUpperCase()}</Text>
      {editing ? (
        <TextInput
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={colors.muted}
          keyboardType={keyboardType}
          autoCapitalize={keyboardType === 'email-address' ? 'none' : 'words'}
          style={[profileFieldStyles.input, { color: colors.text, backgroundColor: colors.cardRaised, borderColor: colors.border }]}
        />
      ) : (
        <Text style={[profileFieldStyles.value, { color: value ? colors.text : colors.muted }]}>{value || placeholder || 'Не указано'}</Text>
      )}
    </View>
  )
}

function Metric({ icon, value, label, colors }: { icon: keyof typeof Ionicons.glyphMap; value: number; label: string; colors: ThemeColors }) {
  return (
    <View style={[metricStyles.item, { backgroundColor: colors.cardRaised, borderColor: colors.border }]}>
      <View style={[metricStyles.icon, { backgroundColor: colors.overlay }]}><Ionicons name={icon} size={19} color={colors.g2} /></View>
      <Text style={[metricStyles.value, { color: colors.text }]}>{value}</Text>
      <Text style={[metricStyles.label, { color: colors.muted }]}>{label}</Text>
    </View>
  )
}

const statStyles = StyleSheet.create({ item: { flex: 1, alignItems: 'center' }, value: { fontSize: 17, fontWeight: '800' }, label: { fontSize: 10, fontWeight: '600', marginTop: 2 } })
const profileFieldStyles = StyleSheet.create({
  row: { paddingVertical: 12, borderBottomWidth: 1 },
  label: { fontSize: 9, fontWeight: '800', letterSpacing: 0.8, marginBottom: 5 },
  value: { fontSize: 14, fontWeight: '600', minHeight: 21 },
  input: { height: 44, borderWidth: 1, borderRadius: 12, paddingHorizontal: 12, fontSize: 14, fontWeight: '600' },
})
const metricStyles = StyleSheet.create({
  item: { width: '48%', minHeight: 104, padding: 13, borderWidth: 1, borderRadius: 15 },
  icon: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  value: { fontSize: 20, fontWeight: '900' },
  label: { fontSize: 10, fontWeight: '600', marginTop: 2 },
})

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
    profileCard: { padding: 16, marginBottom: 24 },
    cardHeading: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 },
    cardTitleNoMargin: { color: colors.text, fontSize: 15, fontWeight: '800' },
    cardHint: { color: colors.muted, fontSize: 10, marginTop: 3 },
    smallAction: { flexDirection: 'row', gap: 5, alignItems: 'center', paddingHorizontal: 10, height: 34, borderRadius: 11, backgroundColor: colors.overlay },
    smallActionText: { color: colors.g2, fontSize: 11, fontWeight: '800' },
    inlineError: { color: colors.danger, fontSize: 11, lineHeight: 16, padding: 10, borderRadius: 10, backgroundColor: colors.dangerSoft, marginBottom: 8 },
    fieldLabel: { color: colors.muted, fontSize: 9, fontWeight: '800', letterSpacing: 0.8 },
    fieldValue: { color: colors.text, fontSize: 14, fontWeight: '600', marginTop: 4 },
    authRow: { minHeight: 65, flexDirection: 'row', alignItems: 'center', gap: 10 },
    authCopy: { flex: 1 },
    emailLinkPanel: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
    emailLinkHeading: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 10 },
    emailLinkHint: { color: colors.sub, fontSize: 11, lineHeight: 16, marginTop: 3 },
    emailCodeInput: { height: 46, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 12, color: colors.text, backgroundColor: colors.cardRaised, fontSize: 16, marginBottom: 9 },
    emailLinkButton: { minHeight: 44, borderRadius: 12, backgroundColor: colors.g2, alignItems: 'center', justifyContent: 'center' },
    emailLinkButtonText: { color: colors.onPrimary, fontSize: 13, fontWeight: '800' },
    emailLinkRetry: { color: colors.g2, fontSize: 11, fontWeight: '700', textAlign: 'center', marginTop: 10 },
    emailLinkMessage: { color: colors.sub, fontSize: 11, lineHeight: 16, marginTop: 9, textAlign: 'center' },
    emailLinkedRow: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 8, borderBottomWidth: 1, borderBottomColor: colors.border },
    emailLinkedText: { color: colors.g2, fontSize: 12, fontWeight: '700' },
    primaryButton: { height: 48, borderRadius: 14, backgroundColor: colors.g2, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
    primaryButtonText: { color: colors.onPrimary, fontSize: 14, fontWeight: '800' },
    buttonDisabled: { opacity: 0.55 },
    journeyCard: { padding: 14, marginBottom: 24 },
    metricGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
    journeyFooter: { flexDirection: 'row', gap: 8, alignItems: 'center', paddingTop: 13, paddingHorizontal: 3 },
    journeyFooterText: { flex: 1, color: colors.sub, fontSize: 11, lineHeight: 16 },
    referralCard: { padding: 16, marginBottom: 24 },
    referralTop: { flexDirection: 'row', justifyContent: 'space-between', gap: 12, alignItems: 'center' },
    referralLink: { color: colors.g2, fontSize: 10, marginTop: 5, maxWidth: 260 },
    shareButton: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.g2 },
    referralStats: { flexDirection: 'row', alignItems: 'center', marginTop: 19, paddingVertical: 14, borderTopWidth: 1, borderBottomWidth: 1, borderColor: colors.border },
    peopleList: { paddingTop: 7 },
    personRow: { minHeight: 59, flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1, borderBottomColor: colors.border },
    personAvatar: { width: 34, height: 34, borderRadius: 11, backgroundColor: colors.overlay, alignItems: 'center', justifyContent: 'center', marginRight: 10 },
    personAvatarText: { color: colors.g2, fontSize: 13, fontWeight: '900' },
    personCopy: { flex: 1 },
    personName: { color: colors.text, fontSize: 12, fontWeight: '800' },
    personMeta: { color: colors.muted, fontSize: 10, marginTop: 3 },
    personSteps: { color: colors.sub, fontSize: 10, fontWeight: '700' },
    charityCard: { padding: 17, marginBottom: 24 },
    charityIcon: { width: 44, height: 44, borderRadius: 14, backgroundColor: colors.goldpale, alignItems: 'center', justifyContent: 'center' },
    charityLead: { position: 'absolute', left: 76, top: 17 },
    charityAmount: { color: colors.text, fontSize: 22, fontWeight: '900' },
    charityLabel: { color: colors.muted, fontSize: 10, marginTop: 2 },
    charityDivider: { height: 1, backgroundColor: colors.border, marginTop: 15, marginBottom: 9 },
    charityRow: { minHeight: 35, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    charityRowLabel: { color: colors.sub, fontSize: 11, fontWeight: '600' },
    charityRowValue: { color: colors.text, fontSize: 12, fontWeight: '800' },
    charityNote: { color: colors.muted, fontSize: 9, lineHeight: 14, marginTop: 9, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border },
    themeCard: { padding: 16, marginBottom: 24 }, cardTitle: { color: colors.text, fontSize: 14, fontWeight: '700', marginBottom: 10 }, paletteGrid: { flexDirection: 'row', gap: 10 },
    paletteOption: { flex: 1, minHeight: 105, borderWidth: 1, borderColor: colors.border, borderRadius: radius.button, padding: 12, backgroundColor: colors.cardRaised }, optionSelected: { borderColor: colors.gold, backgroundColor: colors.overlay },
    swatchRow: { flexDirection: 'row', alignItems: 'center', height: 26, marginBottom: 8 }, swatch: { width: 27, height: 27, borderRadius: 14, borderWidth: 2, borderColor: colors.cardRaised }, swatchOverlap: { marginLeft: -8 }, checkmark: { marginLeft: 'auto' },
    optionLabel: { color: colors.text, fontSize: 13, fontWeight: '700' }, optionLabelSelected: { color: colors.g2 }, optionSub: { color: colors.muted, fontSize: 10, lineHeight: 14, marginTop: 3 },
    modeTitle: { marginTop: 18 }, modeRow: { flexDirection: 'row', gap: 7 }, modeOption: { flex: 1, minHeight: 46, alignItems: 'center', justifyContent: 'center', gap: 3, borderRadius: 12, backgroundColor: colors.cardRaised, borderWidth: 1, borderColor: colors.border }, modeSelected: { borderColor: colors.gold, backgroundColor: colors.overlay }, modeText: { color: colors.muted, fontSize: 10, fontWeight: '700' },
    settingsCard: { paddingHorizontal: 16, marginBottom: 24 }, settingRow: { minHeight: 72, flexDirection: 'row', alignItems: 'center' }, settingIcon: { width: 40, height: 40, borderRadius: 13, backgroundColor: colors.overlay, alignItems: 'center', justifyContent: 'center', marginRight: 12 }, settingCopy: { flex: 1 }, settingTitle: { color: colors.text, fontSize: 14, fontWeight: '700' }, settingSub: { color: colors.muted, fontSize: 11, marginTop: 3 }, separator: { height: 1, backgroundColor: colors.border, marginLeft: 52 },
    installHelp: { flexDirection: 'row', gap: 9, padding: 12, marginBottom: 12, borderRadius: 13, backgroundColor: colors.goldpale }, installHelpCopy: { flex: 1 }, installHelpTitle: { color: colors.text, fontSize: 12, fontWeight: '800', marginBottom: 8 }, installStep: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', marginTop: 5 }, installStepNumber: { width: 19, height: 19, borderRadius: 10, backgroundColor: colors.gold, alignItems: 'center', justifyContent: 'center', marginTop: 1 }, installStepNumberText: { color: colors.onPrimary, fontSize: 10, fontWeight: '900' }, installHelpText: { flex: 1, color: colors.sub, fontSize: 11, lineHeight: 16 }, installHelpNote: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 10 },
    achievementsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 20 }, achievement: { width: '48%', minHeight: 74, padding: 11, flexDirection: 'row', alignItems: 'center', backgroundColor: colors.card, borderRadius: radius.button, ...shadow.card }, achievementLocked: { elevation: 0, shadowOpacity: 0, borderWidth: 1, borderColor: colors.border }, achievementIcon: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.overlay, marginRight: 9 }, achievementIconUnlocked: { backgroundColor: colors.goldpale }, achievementLabel: { flex: 1, color: colors.text, fontSize: 11, lineHeight: 15, fontWeight: '700' }, achievementLabelLocked: { color: colors.muted },
    logoutButton: { minHeight: 52, borderRadius: radius.button, borderWidth: 1, borderColor: colors.dangerSoft, backgroundColor: colors.card, flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center' },
    logoutText: { color: colors.danger, fontSize: 14, fontWeight: '700' },
    deleteAccountButton: { minHeight: 46, flexDirection: 'row', gap: 7, alignItems: 'center', justifyContent: 'center', marginTop: 8 },
    deleteAccountText: { color: colors.danger, fontSize: 12, fontWeight: '700' },
    deleteAccountPanel: { padding: 15, marginTop: 8, borderRadius: radius.button, borderWidth: 1, borderColor: colors.dangerSoft, backgroundColor: colors.card },
    deleteAccountTitle: { color: colors.danger, fontSize: 14, fontWeight: '800' },
    deleteAccountHint: { color: colors.sub, fontSize: 11, lineHeight: 17, marginTop: 7 },
    deleteAccountInput: { height: 46, borderWidth: 1, borderColor: colors.dangerSoft, borderRadius: 12, color: colors.text, backgroundColor: colors.cardRaised, paddingHorizontal: 12, fontSize: 13, fontWeight: '700', marginTop: 12 },
    deleteAccountConfirm: { height: 46, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.danger, marginTop: 10 },
    deleteAccountConfirmText: { color: colors.onPrimary, fontSize: 13, fontWeight: '800' },
    buildTag: { textAlign: 'center', color: colors.muted, fontSize: 10, marginTop: 14 },
  })
}
