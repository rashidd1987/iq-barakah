import { Ionicons } from '@expo/vector-icons'
import * as Application from 'expo-application'
import React, { useMemo, useState } from 'react'
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { LoginStatus, loginWithTelegram } from '../utils/auth'

const STATUS_LABEL: Record<LoginStatus, string> = {
  opening_telegram: 'Открываем Telegram…',
  waiting_confirmation: 'Подтвердите вход в Telegram-боте',
  success: 'Готово!',
  timeout: 'Время ожидания истекло. Попробуйте снова.',
  error: 'Не удалось войти. Попробуйте снова.',
}

export default function LoginScreen() {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
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
      <View style={styles.logo}><Ionicons name="leaf" size={35} color={colors.gold} /></View>
      <Text style={styles.eyebrow}>ПУТЬ К ПОСТОЯНСТВУ</Text>
      <Text style={styles.title}>IQ Barakah</Text>
      <Text style={styles.subtitle}>Малые и постоянные шаги{`\n`}к осознанной жизни</Text>

      <View style={styles.loginCard}>
      <Pressable style={[styles.button, busy && styles.buttonDisabled]} onPress={handleLogin} disabled={busy}>
        {busy ? (
          <ActivityIndicator color={colors.onPrimary} />
        ) : (
          <><Ionicons name="paper-plane" size={19} color={colors.onPrimary} /><Text style={styles.buttonText}>Войти через Telegram</Text></>
        )}
      </Pressable>

      {status && <Text style={styles.status}>{STATUS_LABEL[status]}</Text>}

      <Text style={styles.hint}>
        Вход доступен только участникам программы, уже активированным куратором в боте.
      </Text>
      </View>

      <Text style={styles.buildTag}>build {Application.nativeBuildVersion ?? '?'}</Text>
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
  status: { marginTop: 16, color: colors.sub, textAlign: 'center' },
  hint: { marginTop: 22, color: colors.muted, fontSize: 11, lineHeight: 17, textAlign: 'center', paddingHorizontal: 8 },
  buildTag: { marginTop: 16, color: colors.border, fontSize: 11 },
  })
}
