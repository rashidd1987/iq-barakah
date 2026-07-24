import AsyncStorage from '@react-native-async-storage/async-storage'

const PREFIX = 'iq_'

export async function lsGet<T>(key: string, fallback: T): Promise<T> {
  try {
    const raw = await AsyncStorage.getItem(PREFIX + key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

export async function lsSet<T>(key: string, value: T): Promise<void> {
  await AsyncStorage.setItem(PREFIX + key, JSON.stringify(value))
}

export function todayKey(): string {
  return new Date().toISOString().slice(0, 10)
}
