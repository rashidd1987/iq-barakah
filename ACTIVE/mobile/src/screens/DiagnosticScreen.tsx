import React, { useState } from 'react'
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native'
import { colors, radius, shadow } from '../theme/colors'
import { lsSet } from '../utils/storage'

const OPTIONS = [
  { value: 0, label: '0-1 раз', reflection: 'значит, последние дни прошли почти полностью на автопилоте' },
  { value: 2, label: '2-4 раза', reflection: 'система есть, но держится на честном слове, а не на структуре' },
  { value: 5, label: '5-7 раз', reflection: 'ты близко — не хватает только устойчивой опоры на каждый день' },
]

const REFLECTION_TEXT =
  'Осознанность без системы держится в среднем 2-3 дня — потом человек снова растворяется в автопилоте. ' +
  'Это не слабость характера, это особенность внимания. Система нужна не потому, что ты недостаточно старался, ' +
  'а потому, что даже сильная воля не заменяет структуру.'

interface Props {
  onContinue: () => void
}

export default function DiagnosticScreen({ onContinue }: Props) {
  const [answered, setAnswered] = useState<number | null>(null)

  const handleAnswer = async (value: number) => {
    setAnswered(value)
    await lsSet('seen_diagnostic', true)
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>Прежде чем начать</Text>
      <Text style={styles.question}>
        Сколько раз за последнюю неделю ты по-настоящему был в намазе, а не просто механически его выполнил?
      </Text>

      {answered === null ? (
        <View style={styles.options}>
          {OPTIONS.map((o) => (
            <Pressable key={o.value} style={styles.optionCard} onPress={() => handleAnswer(o.value)}>
              <Text style={styles.optionLabel}>{o.label}</Text>
            </Pressable>
          ))}
        </View>
      ) : (
        <View style={styles.reflectionBlock}>
          <Text style={styles.reflectionPersonal}>
            {OPTIONS.find((o) => o.value === answered)?.reflection}.
          </Text>
          <Text style={styles.reflectionGeneral}>{REFLECTION_TEXT}</Text>
          <Pressable style={styles.continueButton} onPress={onContinue}>
            <Text style={styles.continueButtonText}>Начать строить систему</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 24, paddingTop: 64, flexGrow: 1, justifyContent: 'center' },
  eyebrow: { fontSize: 13, fontWeight: '600', color: colors.gold, marginBottom: 8, textAlign: 'center' },
  question: { fontSize: 20, fontWeight: '700', color: colors.g1, textAlign: 'center', marginBottom: 32, lineHeight: 28 },
  options: { gap: 12 },
  optionCard: {
    backgroundColor: colors.card,
    borderRadius: radius.card,
    padding: 16,
    alignItems: 'center',
    ...shadow.card,
  },
  optionLabel: { fontSize: 16, fontWeight: '600', color: colors.text },
  reflectionBlock: { alignItems: 'center' },
  reflectionPersonal: { fontSize: 16, fontWeight: '600', color: colors.text, textAlign: 'center', marginBottom: 16 },
  reflectionGeneral: { fontSize: 14, color: colors.sub, textAlign: 'center', lineHeight: 21, marginBottom: 28 },
  continueButton: {
    backgroundColor: colors.g2,
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: radius.button,
  },
  continueButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
})
