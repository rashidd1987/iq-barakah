import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import React from 'react'
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

export default function RootNavigator() {
  const { isLoggedIn, isLoading, onboarding, advanceOnboarding } = useAuth()

  if (isLoading || (isLoggedIn && onboarding === null)) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.g2} />
      </View>
    )
  }

  let content
  if (!isLoggedIn) {
    content = <LoginScreen />
  } else if (onboarding === 'diagnostic') {
    content = <DiagnosticScreen onContinue={() => advanceOnboarding('vision')} />
  } else if (onboarding === 'vision') {
    content = <VisionScreen onContinue={() => advanceOnboarding('done')} />
  } else {
    content = <Tabs />
  }

  return <NavigationContainer>{content}</NavigationContainer>
}
