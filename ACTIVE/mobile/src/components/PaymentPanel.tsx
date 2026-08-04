import { Ionicons } from '@expo/vector-icons'
import * as Linking from 'expo-linking'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from 'react-native'
import { useTheme } from '../context/ThemeContext'
import { makeShadow, radius, ThemeColors } from '../theme/colors'
import { api, PaymentTariff } from '../utils/api'
import { lsGet, lsSet } from '../utils/storage'

const PENDING_PAYMENT_KEY = 'pending_payment_id'

export default function PaymentPanel() {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const [tariffs, setTariffs] = useState<PaymentTariff[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState<PaymentTariff['id'] | null>(null)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [paymentMessage, setPaymentMessage] = useState<string | null>(null)

  const loadCatalog = useCallback(async () => {
    try {
      const result = await api.paymentCatalog()
      setTariffs(result.tariffs)
    } catch {
      setPaymentMessage('Оплата временно недоступна. Попробуйте позже или напишите куратору.')
    } finally {
      setLoading(false)
    }
  }, [])

  const checkPayment = useCallback(async (paymentId: string) => {
    try {
      const result = await api.paymentStatus(paymentId)
      if (result.status === 'paid') {
        setPaymentMessage('Оплата подтверждена. Доступ к программе обновлён.')
        setPendingId(null)
        await lsSet(PENDING_PAYMENT_KEY, null)
        await loadCatalog()
      } else if (result.provider_status === 'succeeded') {
        setPaymentMessage('Оплата получена. Активируем программу — обычно это занимает до двух минут.')
      } else if (result.provider_status === 'canceled' || result.status === 'failed') {
        setPaymentMessage('Платёж отменён. Деньги не списаны — можно попробовать снова.')
        setPendingId(null)
        await lsSet(PENDING_PAYMENT_KEY, null)
      } else {
        setPaymentMessage('Ожидаем завершения оплаты.')
      }
    } catch {
      setPaymentMessage('Не удалось проверить платёж. Попробуйте ещё раз через минуту.')
    }
  }, [loadCatalog])

  useEffect(() => {
    loadCatalog()
    lsGet<string | null>(PENDING_PAYMENT_KEY, null).then((value) => {
      if (value) {
        setPendingId(value)
        checkPayment(value)
      }
    })
  }, [checkPayment, loadCatalog])

  useEffect(() => {
    if (!pendingId) return
    const timer = setInterval(() => checkPayment(pendingId), 10_000)
    return () => clearInterval(timer)
  }, [checkPayment, pendingId])

  const startPayment = async (tariff: PaymentTariff) => {
    if (tariff.paid || creating) return
    setCreating(tariff.id)
    setPaymentMessage(null)
    try {
      const result = await api.createPayment(tariff.id)
      await lsSet(PENDING_PAYMENT_KEY, result.payment_id)
      setPendingId(result.payment_id)
      setPaymentMessage('Платёж создан. После оплаты вернитесь в IQ Barakah.')
      await Linking.openURL(result.confirmation_url)
    } catch (error) {
      const text = error instanceof Error && error.message.includes('409')
        ? 'Этот тариф уже оплачен.'
        : 'Не удалось создать платёж. Попробуйте позже.'
      Alert.alert('Оплата', text)
      await loadCatalog()
    } finally {
      setCreating(null)
    }
  }

  return (
    <View>
      <Text style={styles.sectionTitle}>Программы и оплата</Text>
      <View style={styles.card}>
        <View style={styles.heading}>
          <View style={styles.icon}><Ionicons name="shield-checkmark" size={21} color={colors.g2} /></View>
          <View style={styles.headingCopy}>
            <Text style={styles.title}>Безопасная оплата</Text>
            <Text style={styles.subtitle}>Картой или СБП на защищённой странице ЮKassa</Text>
          </View>
        </View>
        {loading ? <ActivityIndicator color={colors.g2} style={styles.loader} /> : tariffs.map((tariff) => (
          <View key={tariff.id} style={styles.tariff}>
            <View style={styles.tariffTop}>
              <View style={styles.tariffCopy}>
                <Text style={styles.tariffName}>{tariff.name}</Text>
                <Text style={styles.tariffDescription}>{tariff.description}</Text>
                {tariff.offer ? <Text style={styles.offer}>{tariff.offer}</Text> : null}
              </View>
              <Text style={styles.price}>{tariff.price.toLocaleString('ru-RU')} ₽</Text>
            </View>
            <Pressable
              style={[styles.payButton, tariff.paid && styles.paidButton, creating === tariff.id && styles.disabled]}
              onPress={() => startPayment(tariff)}
              disabled={tariff.paid || creating !== null}
            >
              {creating === tariff.id ? <ActivityIndicator color={colors.onPrimary} /> : (
                <>
                  <Ionicons name={tariff.paid ? 'checkmark-circle' : 'card-outline'} size={18} color={tariff.paid ? colors.g2 : colors.onPrimary} />
                  <Text style={[styles.payText, tariff.paid && styles.paidText]}>{tariff.paid ? 'Оплачено' : 'Перейти к оплате'}</Text>
                </>
              )}
            </Pressable>
          </View>
        ))}
        {pendingId ? (
          <Pressable style={styles.checkButton} onPress={() => checkPayment(pendingId)}>
            <Ionicons name="refresh" size={17} color={colors.g2} />
            <Text style={styles.checkText}>Проверить оплату</Text>
          </Pressable>
        ) : null}
        {paymentMessage ? <Text style={styles.message}>{paymentMessage}</Text> : null}
        <Text style={styles.note}>Данные карты не передаются IQ Barakah. Доступ активируется в едином аккаунте PWA, приложения и Telegram.</Text>
      </View>
    </View>
  )
}

const createStyles = (colors: ThemeColors) => {
  const shadow = makeShadow(colors)
  return StyleSheet.create({
    sectionTitle: { fontSize: 11, fontWeight: '800', color: colors.muted, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 9, marginLeft: 2 },
    card: { padding: 16, marginBottom: 24, backgroundColor: colors.card, borderRadius: radius.card, ...shadow.card },
    heading: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
    icon: { width: 42, height: 42, borderRadius: 13, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.successSoft, marginRight: 11 },
    headingCopy: { flex: 1 },
    title: { color: colors.text, fontSize: 15, fontWeight: '800' },
    subtitle: { color: colors.muted, fontSize: 10, lineHeight: 15, marginTop: 3 },
    loader: { marginVertical: 24 },
    tariff: { paddingVertical: 14, borderTopWidth: 1, borderTopColor: colors.border },
    tariffTop: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
    tariffCopy: { flex: 1 },
    tariffName: { color: colors.text, fontSize: 13, fontWeight: '800' },
    tariffDescription: { color: colors.sub, fontSize: 10, lineHeight: 15, marginTop: 3 },
    offer: { color: colors.gold, fontSize: 10, fontWeight: '800', marginTop: 5 },
    price: { color: colors.text, fontSize: 16, fontWeight: '900' },
    payButton: { height: 44, borderRadius: 12, backgroundColor: colors.g2, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 7, marginTop: 11 },
    paidButton: { backgroundColor: colors.successSoft, borderWidth: 1, borderColor: colors.border },
    disabled: { opacity: 0.6 },
    payText: { color: colors.onPrimary, fontSize: 12, fontWeight: '800' },
    paidText: { color: colors.g2 },
    checkButton: { height: 42, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6, borderRadius: 11, backgroundColor: colors.overlay, marginTop: 4 },
    checkText: { color: colors.g2, fontSize: 11, fontWeight: '800' },
    message: { color: colors.sub, fontSize: 11, lineHeight: 16, textAlign: 'center', marginTop: 11 },
    note: { color: colors.muted, fontSize: 9, lineHeight: 14, paddingTop: 12, marginTop: 12, borderTopWidth: 1, borderTopColor: colors.border },
  })
}
