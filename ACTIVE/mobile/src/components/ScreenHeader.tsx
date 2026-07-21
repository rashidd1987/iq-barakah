import { LinearGradient } from 'expo-linear-gradient'
import React, { useMemo } from 'react'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { useTheme } from '../context/ThemeContext'
import { radius, ThemeColors } from '../theme/colors'

// Mirrors the miniapp's .hdr — gradient g1→g2→g3, "IQ Barakah" wordmark, badge pill,
// title + subtitle. This is the dominant visual signature of the miniapp; the native
// app used plain white nav-bar headers before, which is why it didn't feel like the
// same product.
interface Props {
  badge: string
  title: string
  subtitle?: string
  children?: React.ReactNode
}

export default function ScreenHeader({ badge, title, subtitle, children }: Props) {
  const { colors, isDark, toggleMode } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  return (
    <LinearGradient
      colors={[colors.g1, colors.g2, colors.g3]}
      start={{ x: 0.1, y: 0 }}
      end={{ x: 0.9, y: 1 }}
      style={styles.hdr}
    >
      <View style={styles.hdrTop}>
        <Text style={styles.logo}>
          IQ <Text style={styles.logoEm}>Barakah</Text>
        </Text>
        <View style={styles.hdrActions}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={isDark ? 'Включить светлую тему' : 'Включить тёмную тему'}
            hitSlop={8}
            style={styles.themeButton}
            onPress={toggleMode}
          >
            <Text style={styles.themeButtonText}>{isDark ? '☀︎' : '◐'}</Text>
          </Pressable>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{badge}</Text>
          </View>
        </View>
      </View>
      <Text style={styles.title}>{title}</Text>
      {!!subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
      {children}
    </LinearGradient>
  )
}

const createStyles = (colors: ThemeColors) => StyleSheet.create({
  hdr: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 28,
    borderBottomLeftRadius: radius.card,
    borderBottomRightRadius: radius.card,
  },
  hdrTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  hdrActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  logo: { fontSize: 17, fontWeight: '800', color: colors.onPrimary, letterSpacing: -0.2 },
  logoEm: { color: colors.gold2 },
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.18)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.25)',
  },
  badgeText: { fontSize: 12, fontWeight: '600', color: colors.onPrimary },
  themeButton: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.22)',
  },
  themeButtonText: { color: colors.gold2, fontSize: 18, fontWeight: '700' },
  title: { fontSize: 24, fontWeight: '800', color: colors.onPrimary, letterSpacing: -0.4, marginBottom: 3 },
  subtitle: { fontSize: 14, color: 'rgba(255,255,255,0.72)' },
})
