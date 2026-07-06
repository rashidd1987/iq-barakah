import * as Application from 'expo-application'
import React, { useState } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native'
import { useAuth } from '../context/AuthContext'
import { colors, radius } from '../theme/colors'
import { LoginStatus, loginWithTelegram } from '../utils/auth'

const STATUS_LABEL: Record<LoginStatus, string> = {
  opening_telegram: 'Открываем Telegram…',
  waiting_confirmation: 'Подтвердите вход в Telegram-боте',
  success: 'Готово!',
  timeout: 'Время ожидания истекло. Попробуйте снова.',
  error: 'Не удалось войти. Попробуйте снова.',
}

export default function LoginScreen() {
  const { markLoggedIn } = useAuth()
  const [status, setStatus] = useState<LoginStatus | null>(null)
  const [busy, setBusy] = useState(false)

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

  return (
    <View style={styles.container}>
      <Text style={styles.logo}>🌱</Text>
      <Text style={styles.title}>IQ Barakah</Text>
      <Text style={styles.subtitle}>Программа личностного развития</Text>

      <Pressable style={styles.button} onPress={handleLogin} disabled={busy}>
        {busy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Войти через Telegram</Text>
        )}
      </Pressable>

      {status && <Text style={styles.status}>{STATUS_LABEL[status]}</Text>}

      <Text style={styles.hint}>
        Вход доступен только участникам программы, уже активированным куратором в боте.
      </Text>

      <Text style={styles.buildTag}>build {Application.nativeBuildVersion ?? '?'}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  logo: { fontSize: 56, marginBottom: 8 },
  title: { fontSize: 28, fontWeight: '700', color: colors.g1, marginBottom: 4 },
  subtitle: { fontSize: 15, color: colors.sub, marginBottom: 32, textAlign: 'center' },
  button: {
    backgroundColor: colors.g2,
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: radius.button,
    minWidth: 240,
    alignItems: 'center',
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  status: { marginTop: 16, color: colors.sub, textAlign: 'center' },
  hint: { marginTop: 40, color: colors.muted, fontSize: 12, textAlign: 'center', paddingHorizontal: 16 },
  buildTag: { marginTop: 16, color: colors.border, fontSize: 11 },
})
