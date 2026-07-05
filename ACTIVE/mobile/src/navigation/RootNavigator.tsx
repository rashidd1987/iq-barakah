import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import React, { useEffect, useState } from 'react'
import { ActivityIndicator, Text, View } from 'react-native'
import { useAuth } from '../context/AuthContext'
import { colors } from '../theme/colors'
import DiagnosticScreen from '../screens/DiagnosticScreen'
import HomeScreen from '../screens/HomeScreen'
import LessonDetailScreen from '../screens/LessonDetailScreen'
import LessonsScreen from '../screens/LessonsScreen'
import LoginScreen from '../screens/LoginScreen'
import ProfileScreen from '../screens/ProfileScreen'
import TrackerScreen from '../screens/TrackerScreen'
import VisionScreen from '../screens/VisionScreen'
import { lsGet, lsSet } from '../utils/storage'
import { LessonsStackParamList, RootTabParamList } from './types'

const Tab = createBottomTabNavigator<RootTabParamList>()
const LessonsStack = createNativeStackNavigator<LessonsStackParamList>()

const TAB_ICONS: Record<keyof RootTabParamList, string> = {
  Home: '🏠',
  Lessons: '📚',
  Tracker: '✅',
  Profile: '👤',
}

function LessonsNavigator() {
  return (
    <LessonsStack.Navigator screenOptions={{ headerTintColor: colors.g1 }}>
      <LessonsStack.Screen name="LessonsList" component={LessonsScreen} options={{ title: 'Уроки' }} />
      <LessonsStack.Screen
        name="LessonDetail"
        component={LessonDetailScreen}
        options={({ route }) => ({ title: `Шаг ${route.params.week}` })}
      />
    </LessonsStack.Navigator>
  )
}

function Tabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerTintColor: colors.g1,
        tabBarActiveTintColor: colors.g2,
        tabBarInactiveTintColor: colors.muted,
        tabBarIcon: () => <Text>{TAB_ICONS[route.name]}</Text>,
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} options={{ title: 'Главная' }} />
      <Tab.Screen name="Lessons" component={LessonsNavigator} options={{ title: 'Уроки', headerShown: false }} />
      <Tab.Screen name="Tracker" component={TrackerScreen} options={{ title: 'Трекер' }} />
      <Tab.Screen name="Profile" component={ProfileScreen} options={{ title: 'Профиль' }} />
    </Tab.Navigator>
  )
}

type OnboardingStage = 'diagnostic' | 'vision' | 'done'

export default function RootNavigator() {
  const { isLoggedIn, isLoading } = useAuth()
  const [onboarding, setOnboarding] = useState<OnboardingStage | null>(null)

  useEffect(() => {
    if (!isLoggedIn) {
      setOnboarding(null)
      return
    }
    lsGet('seen_diagnostic', false).then((seen) => setOnboarding(seen ? 'done' : 'diagnostic'))
  }, [isLoggedIn])

  if (isLoading || (isLoggedIn && onboarding === null)) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.g2} />
      </View>
    )
  }

  const finishOnboarding = () => {
    lsSet('seen_diagnostic', true)
    setOnboarding('done')
  }

  let content
  if (!isLoggedIn) {
    content = <LoginScreen />
  } else if (onboarding === 'diagnostic') {
    content = <DiagnosticScreen onContinue={() => setOnboarding('vision')} />
  } else if (onboarding === 'vision') {
    content = <VisionScreen onContinue={finishOnboarding} />
  } else {
    content = <Tabs />
  }

  return <NavigationContainer>{content}</NavigationContainer>
}
