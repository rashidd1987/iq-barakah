import React, { useMemo } from 'react'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { useTheme } from '../context/ThemeContext'
import { radius, ThemeColors } from '../theme/colors'

interface Props {
  message?: string
  onRetry: () => void
}

export default function ErrorState({ message = 'Не удалось загрузить данные', onRetry }: Props) {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>⚠️</Text>
      <Text style={styles.message}>{message}</Text>
      <Text style={styles.hint}>Проверьте интернет-соединение</Text>
      <Pressable style={styles.button} onPress={onRetry}>
        <Text style={styles.buttonText}>Повторить</Text>
      </Pressable>
    </View>
  )
}

const createStyles = (colors: ThemeColors) => StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: colors.bg },
  icon: { fontSize: 32, marginBottom: 12 },
  message: { fontSize: 15, fontWeight: '600', color: colors.text, textAlign: 'center' },
  hint: { fontSize: 13, color: colors.muted, marginTop: 4, marginBottom: 20, textAlign: 'center' },
  button: {
    backgroundColor: colors.g2,
    paddingVertical: 10,
    paddingHorizontal: 24,
    borderRadius: radius.button,
  },
  buttonText: { color: colors.onPrimary, fontSize: 14, fontWeight: '600' },
})
