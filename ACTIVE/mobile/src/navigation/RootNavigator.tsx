import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { DarkTheme, DefaultTheme, NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import React, { useMemo } from 'react'
import { ActivityIndicator, Text, View } from 'react-native'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import ActivityFeedScreen from '../screens/ActivityFeedScreen'
import DiagnosticScreen from '../screens/DiagnosticScreen'
import HomeScreen from '../screens/HomeScreen'
import LessonDetailScreen from '../screens/LessonDetailScreen'
import LessonsScreen from '../screens/LessonsScreen'
import LoginScreen from '../screens/LoginScreen'
import MuhasabaScreen from '../screens/MuhasabaScreen'
import ProfileScreen from '../screens/ProfileScreen'
import TrackerScreen from '../screens/TrackerScreen'
import VisionScreen from '../screens/VisionScreen'
import WheelScreen from '../screens/WheelScreen'
import { HomeStackParamList, LessonsStackParamList, RootTabParamList } from './types'

const Tab = createBottomTabNavigator<RootTabParamList>()
const LessonsStack = createNativeStackNavigator<LessonsStackParamList>()
const HomeStack = createNativeStackNavigator<HomeStackParamList>()

const TAB_ICONS: Record<keyof RootTabParamList, string> = {
  Home: '🏠',
  Lessons: '📚',
  Tracker: '✅',
  Wheel: '🎯',
  Profile: '👤',
}

function LessonsNavigator() {
  const { colors } = useTheme()
  return (
    <LessonsStack.Navigator screenOptions={{ headerTintColor: colors.g1 }}>
      <LessonsStack.Screen name="LessonsList" component={LessonsScreen} options={{ headerShown: false }} />
      <LessonsStack.Screen
        name="LessonDetail"
        component={LessonDetailScreen}
        options={({ route }) => ({ title: `Шаг ${route.params.week}` })}
      />
    </LessonsStack.Navigator>
  )
}

function HomeNavigator() {
  const { colors } = useTheme()
  return (
    <HomeStack.Navigator screenOptions={{ headerTintColor: colors.g1 }}>
      <HomeStack.Screen name="HomeMain" component={HomeScreen} options={{ headerShown: false }} />
      <HomeStack.Screen name="Muhasaba" component={MuhasabaScreen} options={{ title: 'Вечерний самоотчёт' }} />
      <HomeStack.Screen name="ActivityFeed" component={ActivityFeedScreen} options={{ headerShown: false }} />
    </HomeStack.Navigator>
  )
}

function Tabs() {
  const { colors } = useTheme()
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerTintColor: colors.g1,
        tabBarActiveTintColor: colors.g2,
        tabBarInactiveTintColor: colors.muted,
        tabBarIcon: () => <Text>{TAB_ICONS[route.name]}</Text>,
      })}
    >
      <Tab.Screen name="Home" component={HomeNavigator} options={{ title: 'Главная', headerShown: false }} />
      <Tab.Screen name="Lessons" component={LessonsNavigator} options={{ title: 'Уроки', headerShown: false }} />
      <Tab.Screen name="Tracker" component={TrackerScreen} options={{ title: 'Трекер', headerShown: false }} />
      <Tab.Screen name="Wheel" component={WheelScreen} options={{ title: 'Баланс', headerShown: false }} />
      <Tab.Screen name="Profile" component={ProfileScreen} options={{ title: 'Профиль', headerShown: false }} />
    </Tab.Navigator>
  )
}

export default function RootNavigator() {
  const { isLoggedIn, isLoading, onboarding, advanceOnboarding } = useAuth()
  const { colors, isDark } = useTheme()
  const navigationTheme = useMemo(
    () => ({
      ...(isDark ? DarkTheme : DefaultTheme),
      colors: {
        ...(isDark ? DarkTheme.colors : DefaultTheme.colors),
        primary: colors.g2,
        background: colors.bg,
        card: colors.card,
        text: colors.text,
        border: colors.border,
        notification: colors.gold,
      },
    }),
    [colors, isDark],
  )

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

  return <NavigationContainer theme={navigationTheme}>{content}</NavigationContainer>
}
