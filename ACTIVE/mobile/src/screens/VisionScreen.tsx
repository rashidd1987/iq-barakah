import React, { useMemo } from 'react'
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { useTheme } from '../context/ThemeContext'
import { makeShadow, radius, ThemeColors } from '../theme/colors'

const TRAITS = [
  'Просыпается с ниятом, а не с телефоном в руке',
  'Держит слово — себе и своей семье',
  'Не разрывается между тем, кто он в мечети, и кто он дома',
  'Знает, ради чего живёт каждый конкретный день',
]

interface Props {
  onContinue: () => void
}

export default function VisionScreen({ onContinue }: Props) {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>Через 30 шагов</Text>
      <Text style={styles.title}>Вот кем ты станешь</Text>

      <View style={styles.card}>
        {TRAITS.map((trait, i) => (
          <View key={i} style={styles.traitRow}>
            <Text style={styles.traitIcon}>🌱</Text>
            <Text style={styles.traitText}>{trait}</Text>
          </View>
        ))}
      </View>

      <Text style={styles.footnote}>
        Это не мотивация на один день. Это система, шаг за шагом — с намазом, привычками и честным отчётом
        каждый вечер.
      </Text>

      <Pressable style={styles.continueButton} onPress={onContinue}>
        <Text style={styles.continueButtonText}>Начать путь — Шаг 1</Text>
      </Pressable>
    </ScrollView>
  )
}

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 24, paddingTop: 64, flexGrow: 1, justifyContent: 'center' },
  eyebrow: { fontSize: 13, fontWeight: '600', color: colors.gold, textAlign: 'center', marginBottom: 4 },
  title: { fontSize: 24, fontWeight: '800', color: colors.g1, textAlign: 'center', marginBottom: 28 },
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 20,
    marginBottom: 24,
    ...shadow.card,
  },
  traitRow: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 16 },
  traitIcon: { fontSize: 18, marginRight: 12, marginTop: 1 },
  traitText: { flex: 1, fontSize: 15, fontWeight: '600', color: colors.text, lineHeight: 21 },
  footnote: { fontSize: 13, color: colors.sub, textAlign: 'center', lineHeight: 20, marginBottom: 28 },
  continueButton: {
    backgroundColor: colors.g2,
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: radius.button,
    alignSelf: 'center',
  },
  continueButtonText: { color: colors.onPrimary, fontSize: 16, fontWeight: '600' },
  })
}
