import React, { useCallback, useMemo, useState } from 'react'
import { useFocusEffect } from '@react-navigation/native'
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native'
import ErrorState from '../components/ErrorState'
import ScreenHeader from '../components/ScreenHeader'
import { useTheme } from '../context/ThemeContext'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { api, ActivityItem } from '../utils/api'

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'только что'
  if (minutes < 60) return `${minutes} мин назад`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} ч назад`
  const days = Math.floor(hours / 24)
  return `${days} дн назад`
}

export default function ActivityFeedScreen() {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const [items, setItems] = useState<ActivityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = useCallback(() => {
    setError(false)
    api
      .activityFeed(30)
      .then(setItems)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  useFocusEffect(
    useCallback(() => {
      load()
    }, [load]),
  )

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.g2} />
      </View>
    )
  }

  if (error && items.length === 0) {
    return <ErrorState message="Не удалось загрузить ленту" onRetry={load} />
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      <ScreenHeader badge="Джамаат" title="Лента побед" subtitle="Кто чего достиг на пути — читай, вдохновляйся" />
      <View style={styles.body}>
        {items.length === 0 && <View style={styles.empty}><View style={styles.emptyIcon}><Ionicons name="people-outline" size={29} color={colors.gold} /></View><Text style={styles.emptyTitle}>Пока здесь тихо</Text><Text style={styles.emptyText}>Заверши шаг и стань первым в ленте побед.</Text></View>}
        {items.map((item, i) => (
          <View key={i} style={[styles.card, item.is_me && styles.cardMe]}>
            <View style={styles.icon}><Ionicons name="sparkles" size={20} color={colors.gold} /></View>
            <View style={styles.info}>
              <Text style={styles.text}>
                <Text style={styles.name}>{item.is_me ? 'Ты' : item.first_name}</Text> прошёл Шаг {item.global_week}
              </Text>
              <Text style={styles.time}>{timeAgo(item.acked_at)}</Text>
            </View>
          </View>
        ))}
      </View>
    </ScrollView>
  )
}

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  content: { paddingBottom: 32 },
  body: { padding: 16, marginTop: -16 },
  empty: { alignItems: 'center', backgroundColor: colors.card, borderRadius: radius.card, padding: 28, marginTop: 8, ...shadow.card },
  emptyIcon: { width: 58, height: 58, borderRadius: 20, backgroundColor: colors.goldpale, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  emptyTitle: { color: colors.text, fontSize: 16, fontWeight: '800' }, emptyText: { color: colors.muted, fontSize: 13, lineHeight: 19, textAlign: 'center', marginTop: 5 },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 14,
    marginBottom: 8,
    ...shadow.card,
  },
  cardMe: { backgroundColor: colors.gpale },
  icon: { width: 40, height: 40, borderRadius: 13, backgroundColor: colors.goldpale, alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  info: { flex: 1 },
  text: { fontSize: 14, color: colors.text },
  name: { fontWeight: '700', color: colors.g2 },
  time: { fontSize: 12, color: colors.muted, marginTop: 2 },
  })
}
import { Ionicons } from '@expo/vector-icons'
