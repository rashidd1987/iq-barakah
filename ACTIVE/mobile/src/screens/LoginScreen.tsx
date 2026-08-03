import * as Application from 'expo-application'
import { Ionicons } from '@expo/vector-icons'
import React, { useMemo, useState } from 'react'
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { LoginStatus, loginWithTelegram } from '../utils/auth'
import { ApiError, api, setToken } from '../utils/api'

const STATUS_LABEL: Record<LoginStatus, string> = {
  opening_telegram: 'Открываем Telegram…',
  waiting_confirmation: 'Подтвердите вход в Telegram-боте',
  success: 'Готово!',
  timeout: 'Время ожидания истекло. Попробуйте снова.',
  not_active: 'Доступ к программе ещё не активирован куратором.',
  expired: 'Ссылка входа устарела. Нажмите кнопку ещё раз.',
  error: 'Не удалось войти. Попробуйте снова.',
}

export default function LoginScreen() {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const { markLoggedIn } = useAuth()
  const [status, setStatus] = useState<LoginStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [emailMode, setEmailMode] = useState(false)
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [challengeId, setChallengeId] = useState<string | null>(null)
  const [emailMessage, setEmailMessage] = useState<string | null>(null)

  const handleLogin = async () => {
    setBusy(true)
    try {
      const ok = await loginWithTelegram({ onStatus: setStatus })
      if (ok) markLoggedIn()
    } catch {
      setStatus('error')
    } finally {
      setBusy(false)
    }
  }

  const handleEmailRequest = async () => {
    const value = email.trim().toLowerCase()
    if (!value || !value.includes('@')) {
      setEmailMessage('Введите корректный email.')
      return
    }
    setBusy(true)
    setEmailMessage(null)
    try {
      const result = await api.requestEmailOtp(value)
      setChallengeId(result.challenge_id)
      setEmailMessage('Код отправлен. Проверьте почту.')
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setEmailMessage('Этот email уже связан с другим аккаунтом.')
      } else if (error instanceof ApiError && error.status === 429) {
        setEmailMessage('Слишком много запросов. Попробуйте немного позже.')
      } else {
        setEmailMessage('Не удалось отправить код. Попробуйте позже.')
      }
    } finally {
      setBusy(false)
    }
  }

  const handleEmailVerify = async () => {
    if (!challengeId || !/^\d{6}$/.test(code.trim())) {
      setEmailMessage('Введите шестизначный код из письма.')
      return
    }
    setBusy(true)
    setEmailMessage(null)
    try {
      const result = await api.verifyEmailOtp(challengeId, code.trim())
      await setToken(result.access_token)
      markLoggedIn()
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        setEmailMessage('Этот email ещё не привязан к активному участнику. Сначала войдите через Telegram один раз.')
      } else {
        setEmailMessage('Код неверный или устарел. Запросите новый.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.logo}><Ionicons name="leaf" size={35} color={colors.gold} /></View>
      <Text style={styles.eyebrow}>ПУТЬ К ПОСТОЯНСТВУ</Text>
      <Text style={styles.title}>IQ Barakah</Text>
      <Text style={styles.subtitle}>Малые и постоянные шаги{`\n`}к осознанной жизни</Text>

      <View style={styles.loginCard}>
        {emailMode ? (
        <>
          <Text style={styles.emailTitle}>Вход по email</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder="your@email.com"
            placeholderTextColor={colors.muted}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            editable={!busy && !challengeId}
          />
          {challengeId ? (
            <TextInput
              style={styles.input}
              value={code}
              onChangeText={(value) => setCode(value.replace(/\D/g, '').slice(0, 6))}
              placeholder="Код из письма"
              placeholderTextColor={colors.muted}
              keyboardType="number-pad"
              autoComplete="one-time-code"
              maxLength={6}
              editable={!busy}
            />
          ) : null}
          <Pressable
            style={[styles.button, busy && styles.buttonDisabled]}
            onPress={challengeId ? handleEmailVerify : handleEmailRequest}
            disabled={busy}
          >
            {busy ? <ActivityIndicator color={colors.onPrimary} /> : (
              <Text style={styles.buttonText}>{challengeId ? 'Войти' : 'Получить код'}</Text>
            )}
          </Pressable>
          {challengeId ? (
            <Pressable onPress={() => { setChallengeId(null); setCode(''); setEmailMessage(null) }} disabled={busy}>
              <Text style={styles.link}>Изменить email или запросить новый код</Text>
            </Pressable>
          ) : null}
          {emailMessage ? <Text style={styles.status}>{emailMessage}</Text> : null}
          <Pressable onPress={() => { setEmailMode(false); setEmailMessage(null) }} disabled={busy}>
            <Text style={styles.link}>← Другие способы входа</Text>
          </Pressable>
        </>
        ) : (
          <>
            <Pressable style={[styles.button, busy && styles.buttonDisabled]} onPress={handleLogin} disabled={busy}>
              {busy ? (
                <ActivityIndicator color={colors.onPrimary} />
              ) : (
                <><Ionicons name="paper-plane" size={19} color={colors.onPrimary} /><Text style={styles.buttonText}>Войти через Telegram</Text></>
              )}
            </Pressable>

            {status && <Text style={styles.status}>{STATUS_LABEL[status]}</Text>}

            <Pressable style={styles.emailButton} onPress={() => { setEmailMode(true); setStatus(null) }} disabled={busy}>
              <Ionicons name="mail-outline" size={19} color={colors.g2} />
              <Text style={styles.emailButtonText}>Войти по email</Text>
            </Pressable>

            <Text style={styles.hint}>
              Первый вход и активация — через Telegram. После привязки email можно входить без Telegram.
            </Text>
          </>
        )}
      </View>

      {Platform.OS !== 'web' && Application.nativeBuildVersion ? (
        <Text style={styles.buildTag}>build {Application.nativeBuildVersion}</Text>
      ) : null}
    </View>
  )
}

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  logo: { width: 76, height: 76, borderRadius: 26, backgroundColor: colors.goldpale, alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  eyebrow: { fontSize: 10, fontWeight: '800', letterSpacing: 1.3, color: colors.gold, marginBottom: 7 },
  title: { fontSize: 31, fontWeight: '800', color: colors.text, marginBottom: 7 },
  subtitle: { fontSize: 15, lineHeight: 22, color: colors.sub, marginBottom: 28, textAlign: 'center' },
  loginCard: { width: '100%', maxWidth: 380, backgroundColor: colors.card, borderRadius: radius.card, padding: 18, ...shadow.card },
  button: {
    backgroundColor: colors.g2,
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: radius.button,
    minHeight: 52, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 9,
  },
  buttonDisabled: { opacity: 0.75 },
  buttonText: { color: colors.onPrimary, fontSize: 16, fontWeight: '600' },
  emailTitle: { color: colors.text, fontSize: 18, fontWeight: '700', marginBottom: 12, textAlign: 'center' },
  input: {
    minHeight: 50, borderWidth: 1, borderColor: colors.border, borderRadius: radius.button,
    paddingHorizontal: 14, color: colors.text, backgroundColor: colors.bg, marginBottom: 12, fontSize: 16,
  },
  emailButton: {
    minHeight: 50, marginTop: 12, borderWidth: 1, borderColor: colors.border,
    borderRadius: radius.button, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 9,
  },
  emailButtonText: { color: colors.g2, fontSize: 15, fontWeight: '600' },
  link: { marginTop: 14, color: colors.g2, fontSize: 13, fontWeight: '600', textAlign: 'center' },
  status: { marginTop: 16, color: colors.sub, textAlign: 'center' },
  hint: { marginTop: 22, color: colors.muted, fontSize: 11, lineHeight: 17, textAlign: 'center', paddingHorizontal: 8 },
  buildTag: { marginTop: 16, color: colors.border, fontSize: 11 },
  })
}
