import * as Device from 'expo-device'
import * as Notifications from 'expo-notifications'
import { Platform } from 'react-native'
import { api } from './api'

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
})

// Registers this device for Expo push and links the token to the logged-in user via POST /push/register.
export async function registerForPushNotifications(): Promise<string | null> {
  if (!Device.isDevice) return null // push tokens require a real device, not a simulator

  const { status: existing } = await Notifications.getPermissionsAsync()
  let status = existing
  if (existing !== 'granted') {
    const requested = await Notifications.requestPermissionsAsync()
    status = requested.status
  }
  if (status !== 'granted') return null

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.DEFAULT,
    })
  }

  const { data: expoToken } = await Notifications.getExpoPushTokenAsync()
  await api.registerPush(expoToken, Platform.OS)
  return expoToken
}
