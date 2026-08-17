import { Ionicons } from '@expo/vector-icons'
import * as Linking from 'expo-linking'
import React, { useEffect, useMemo, useRef, useState } from 'react'
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
  const [message, setMessage] = useState<string | null>(null)
  const sessionRef = useRef<string | null>(null)

  const check = async () => {
    const sessionId = sessionRef.current
    if (!sessionId) return
    try {
      const result = await api.telegramLinkCheck(sessionId)
      if (result.status !== 'pending') {
        sessionRef.current = null
        await acceptSession(result.status, result.access_token)
        setBusy(false)
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setMessage('Этот Telegram уже связан с другим аккаунтом. Выйдите и войдите через Telegram.')
        sessionRef.current = null
        setBusy(false)
      } else if (error instanceof ApiError && (error.status === 404 || error.status === 410)) {
        setMessage('Срок подтверждения истёк. Нажмите «Привязать Telegram» ещё раз.')
        sessionRef.current = null
        setBusy(false)
      }
    }
  }

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') void check()
    })
    const timer = setInterval(() => void check(), 2000)
    return () => { subscription.remove(); clearInterval(timer) }
  }, [])

  const startLink = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const result = await api.telegramLinkInit()
      if (result.status === 'already_linked') {
        await refreshSession()
        return
      }
      if (!result.session_id) throw new Error('missing session')
      sessionRef.current = result.session_id
      await Linking.openURL(
        `https://t.me/${BOT_USERNAME}?start=pwa_${encodeURIComponent(result.session_id)}`,
      )
    } catch {
      setBusy(false)
      setMessage('Не удалось открыть Telegram. Проверьте интернет и попробуйте снова.')
    }
  }

  const activationRequired = authStage === 'activation_required'
  return (
    <View style={styles.container}>
      <View style={styles.icon}>
        <Ionicons name={activationRequired ? 'time-outline' : 'git-merge-outline'} size={36} color={colors.gold} />
      </View>
      <Text style={styles.title}>{activationRequired ? 'Telegram привязан' : 'Свяжем аккаунты'}</Text>
      <Text style={styles.text}>
        {activationRequired
          ? 'Аккаунты уже синхронизированы. Осталось дождаться активации программы куратором.'
          : 'Подтвердите свой Telegram один раз. После этого PWA, приложение, миниапп и бот будут видеть один прогресс.'}
      </Text>
      <View style={styles.card}>
        <Pressable style={[styles.button, busy && styles.disabled]} onPress={activationRequired ? refreshSession : startLink} disabled={busy}>
          {busy ? <ActivityIndicator color={colors.onPrimary} /> : (
            <>
              <Ionicons name={activationRequired ? 'refresh' : 'paper-plane'} size={19} color={colors.onPrimary} />
              <Text style={styles.buttonText}>{activationRequired ? 'Проверить активацию' : 'Привязать Telegram'}</Text>
            </>
          )}
        </Pressable>
        {busy && !activationRequired ? <Text style={styles.status}>Подтвердите вход в боте и вернитесь сюда…</Text> : null}
        {message ? <Text style={styles.error}>{message}</Text> : null}
      </View>
      <Pressable onPress={logout}><Text style={styles.link}>Войти с другим email</Text></Pressable>
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
  link: { color: colors.g2, fontWeight: '600', marginTop: 20 },
})
