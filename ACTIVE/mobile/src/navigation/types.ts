export type LessonsStackParamList = {
  LessonsList: undefined
  LessonDetail: { level: string; week: number; globalWeek: number; autoStartQuiz?: boolean }
}

export type HomeStackParamList = {
  HomeMain: undefined
  Muhasaba: undefined
  ActivityFeed: undefined
}

export type RootTabParamList = {
  Home: undefined
  Lessons: undefined
  Tracker: undefined
  Wheel: undefined
  Profile: undefined
}
