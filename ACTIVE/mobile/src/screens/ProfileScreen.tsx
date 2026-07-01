import React, { useEffect, useState } from 'react'
import { Alert, Pressable, StyleSheet, Switch, Text, View } from 'react-native'
import { useAuth } from '../context/AuthContext'
import { colors, radius, shadow } from '../theme/colors'
import { api } from '../utils/api'
import { registerForPushNotifications } from '../utils/push'

export default function ProfileScreen() {
  const { logout } = useAuth()
  const [level, setLevel] = useState<string | null>(null)
  const [week, setWeek] = useState<number | null>(null)
  const [pushEnabled, setPushEnabled] = useState(false)
  const [togglingPush, setTogglingPush] = useState(false)

  useEffect(() => {
    api.participant().then((p) => {
      setLevel(p.level)
      setWeek(p.week)
    })
  }, [])

  const handlePushToggle = async (value: boolean) => {
    setTogglingPush(true)
    try {
      if (value) {
        const token = await registerForPushNotifications()
        if (!token) {
          Alert.alert('Уведомления недоступны', 'Разрешите уведомления в настройках устройства.')
          setPushEnabled(false)
          return
        }
      }
      setPushEnabled(value)
    } finally {
      setTogglingPush(false)
    }
  }

  return (
    <View style={styles.container}>
      <View style={[styles.card, styles.infoCard]}>
        <Text style={styles.infoLabel}>Уровень</Text>
        <Text style={styles.infoValue}>{level ?? '—'}</Text>
        <Text style={styles.infoLabel}>Неделя</Text>
        <Text style={styles.infoValue}>{week ?? '—'}</Text>
      </View>

      <View style={[styles.card, styles.row]}>
        <Text style={styles.rowLabel}>Push-напоминания (Фаджр, пятница)</Text>
        <Switch value={pushEnabled} onValueChange={handlePushToggle} disabled={togglingPush} />
      </View>

      <Pressable style={styles.logoutButton} onPress={logout}>
        <Text style={styles.logoutText}>Выйти</Text>
      </Pressable>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, padding: 16 },
  card: { backgroundColor: colors.card, borderRadius: radius.card, ...shadow.card },
  infoCard: { padding: 16, marginBottom: 12 },
  infoLabel: { fontSize: 12, color: colors.sub, marginTop: 8 },
  infoValue: { fontSize: 18, fontWeight: '700', color: colors.text },
  row: { padding: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  rowLabel: { fontSize: 14, color: colors.text, flex: 1, marginRight: 12 },
  logoutButton: { marginTop: 16, alignItems: 'center', padding: 12 },
  logoutText: { color: colors.muted, fontSize: 14 },
})
