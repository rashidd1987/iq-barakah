import { Ionicons } from '@expo/vector-icons'
import * as Linking from 'expo-linking'
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ActivityIndicator, AppState, Pressable, StyleSheet, Text, View } from 'react-native'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { ApiError, api } from '../utils/api'

const BOT_USERNAME = process.env.EXPO_PUBLIC_BOT_USERNAME || 'iqbaraka_bot'

export default function TelegramLinkScreen() {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const { authStage, acceptSession, refreshSession, logout } = useAuth()
  const [busy, setBusy] = useState(false)
  const [checking, setChecking] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const sessionRef = useRef<string | null>(null)
  const checkInFlightRef = useRef(false)

  const check = useCallback(async () => {
    const sessionId = sessionRef.current
    if (!sessionId || checkInFlightRef.current) return
    checkInFlightRef.current = true
    setChecking(true)
    try {
      const result = await api.telegramLinkCheck(sessionId)
      if (result.status !== 'pending') {
        sessionRef.current = null
        await acceptSession(result.status, result.access_token)
        setBusy(false)
      }
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        setMessage('Сессия входа недействительна. Войдите по email ещё раз.')
        sessionRef.current = null
        setBusy(false)
      } else if (error instanceof ApiError && error.status === 409) {
        setMessage('Этот Telegram уже связан с другим аккаунтом. Выйдите и войдите через Telegram.')
        sessionRef.current = null
        setBusy(false)
      } else if (error instanceof ApiError && (error.status === 404 || error.status === 410)) {
        setMessage('Срок подтверждения истёк. Нажмите «Привязать Telegram» ещё раз.')
        sessionRef.current = null
        setBusy(false)
      } else {
        setMessage('Временная ошибка сети. Подтверждение сохранено — нажмите «Повторить проверку».')
        setBusy(false)
      }
    } finally {
      checkInFlightRef.current = false
      setChecking(false)
    }
  }, [acceptSession])

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') check().catch(() => undefined)
    })
    const timer = setInterval(() => check().catch(() => undefined), 2000)
    return () => { subscription.remove(); clearInterval(timer) }
  }, [check])

  const startLink = async () => {
    setBusy(true)
    setMessage(null)
    let sessionId: string
    try {
      const result = await api.telegramLinkInit()
      if (result.status === 'already_linked') {
        await refreshSession()
        setBusy(false)
        return
      }
      if (!result.session_id) throw new Error('missing session')
      sessionId = result.session_id
      sessionRef.current = sessionId
    } catch (error) {
      setBusy(false)
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        setMessage('Сессия входа недействительна. Войдите по email ещё раз.')
      } else if (error instanceof ApiError && error.status === 409) {
        setMessage('Этот Telegram уже связан с другим аккаунтом. Войдите через связанный Telegram.')
      } else if (error instanceof ApiError && (error.status === 404 || error.status === 410)) {
        setMessage('Сессия привязки больше недоступна. Начните подтверждение заново.')
      } else {
        setMessage('Сервис временно недоступен. Токен сохранён — повторите попытку позже.')
      }
      return
    }

    try {
      await Linking.openURL(
        `https://t.me/${BOT_USERNAME}?start=pwa_${encodeURIComponent(sessionId)}`,
      )
    } catch {
      sessionRef.current = null
      setBusy(false)
      setMessage('Не удалось открыть Telegram. Откройте приложение Telegram и повторите попытку.')
    }
  }

  const retrySession = async () => {
    setBusy(true)
    setMessage(null)
    try {
      await refreshSession()
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        setMessage('Сессия входа недействительна. Войдите по email ещё раз.')
      } else if (error instanceof ApiError && error.status === 409) {
        setMessage('Telegram уже связан с другим аккаунтом. Войдите через связанный аккаунт.')
      } else if (error instanceof ApiError && (error.status === 404 || error.status === 410)) {
        setMessage('Аккаунт или сессия больше не доступны. Войдите заново.')
      } else {
        setMessage('Сервис временно недоступен. Токен сохранён — попробуйте ещё раз позже.')
      }
    } finally {
      setBusy(false)
    }
  }

  const switchAccount = async () => {
    setMessage(null)
    try {
      await logout()
    } catch {
      setMessage('Не удалось завершить локальную сессию. Попробуйте ещё раз.')
    }
  }

  const activationRequired = authStage === 'activation_required'
  const sessionUnavailable = authStage === 'session_unavailable'
  return (
    <View style={styles.container}>
      <View style={styles.icon}>
        <Ionicons name={activationRequired ? 'time-outline' : sessionUnavailable ? 'cloud-offline-outline' : 'git-merge-outline'} size={36} color={colors.gold} />
      </View>
      <Text style={styles.title}>{activationRequired ? 'Telegram привязан' : sessionUnavailable ? 'Связь временно недоступна' : 'Свяжем аккаунты'}</Text>
      <Text style={styles.text}>
        {activationRequired
          ? 'Аккаунты уже синхронизированы. Осталось дождаться активации программы куратором.'
          : sessionUnavailable
            ? 'Сессия сохранена. Проверьте интернет и повторите безопасную проверку.'
          : 'Подтвердите свой Telegram один раз. После этого PWA, приложение, миниапп и бот будут видеть один прогресс.'}
      </Text>
      <View style={styles.card}>
        <Pressable style={[styles.button, (busy || checking) && styles.disabled]} onPress={activationRequired || sessionUnavailable ? retrySession : startLink} disabled={busy || checking}>
          {busy || checking ? <ActivityIndicator color={colors.onPrimary} /> : (
            <>
              <Ionicons name={activationRequired || sessionUnavailable ? 'refresh' : 'paper-plane'} size={19} color={colors.onPrimary} />
              <Text style={styles.buttonText}>{activationRequired ? 'Проверить активацию' : sessionUnavailable ? 'Повторить проверку' : 'Привязать Telegram'}</Text>
            </>
          )}
        </Pressable>
        {busy && !activationRequired ? <Text style={styles.status}>Подтвердите вход в боте и вернитесь сюда…</Text> : null}
        {!busy && !checking && sessionRef.current && message ? (
          <Pressable onPress={() => check().catch(() => undefined)}><Text style={styles.retry}>Повторить проверку Telegram</Text></Pressable>
        ) : null}
        {message ? <Text style={styles.error}>{message}</Text> : null}
      </View>
      <Pressable onPress={() => switchAccount().catch(() => undefined)}>
        <Text style={styles.link}>Войти с другим email</Text>
      </Pressable>
    </View>
  )
}

const createStyles = (colors: ThemeColors) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center', padding: 24 },
  icon: { width: 76, height: 76, borderRadius: 26, backgroundColor: colors.goldpale, alignItems: 'center', justifyContent: 'center', marginBottom: 18 },
  title: { color: colors.text, fontSize: 27, fontWeight: '800', marginBottom: 10, textAlign: 'center' },
  text: { color: colors.sub, fontSize: 15, lineHeight: 22, textAlign: 'center', maxWidth: 390, marginBottom: 22 },
  card: { width: '100%', maxWidth: 390, padding: 18, backgroundColor: colors.card, borderRadius: radius.card, ...makeShadow(colors).card },
  button: { minHeight: 52, borderRadius: radius.button, backgroundColor: colors.g2, flexDirection: 'row', gap: 9, alignItems: 'center', justifyContent: 'center' },
  disabled: { opacity: 0.75 },
  buttonText: { color: colors.onPrimary, fontSize: 16, fontWeight: '700' },
  status: { color: colors.sub, marginTop: 14, textAlign: 'center' },
  error: { color: colors.danger, marginTop: 14, textAlign: 'center' },
  retry: { color: colors.g2, marginTop: 12, textAlign: 'center', fontWeight: '700' },
  link: { color: colors.g2, fontWeight: '600', marginTop: 20 },
})
