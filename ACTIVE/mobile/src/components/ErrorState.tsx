import React from 'react'
import { Pressable, StyleSheet, Text, View } from 'react-native'
import { colors, radius } from '../theme/colors'

interface Props {
  message?: string
  onRetry: () => void
}

export default function ErrorState({ message = 'Не удалось загрузить данные', onRetry }: Props) {
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

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  icon: { fontSize: 32, marginBottom: 12 },
  message: { fontSize: 15, fontWeight: '600', color: colors.text, textAlign: 'center' },
  hint: { fontSize: 13, color: colors.muted, marginTop: 4, marginBottom: 20, textAlign: 'center' },
  button: {
    backgroundColor: colors.g2,
    paddingVertical: 10,
    paddingHorizontal: 24,
    borderRadius: radius.button,
  },
  buttonText: { color: '#fff', fontSize: 14, fontWeight: '600' },
})
