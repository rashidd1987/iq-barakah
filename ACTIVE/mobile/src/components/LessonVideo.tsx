import { useVideoPlayer, VideoView } from 'expo-video'
import React, { useMemo } from 'react'
import { StyleSheet, Text, View } from 'react-native'
import { useTheme } from '../context/ThemeContext'
import { radius, ThemeColors } from '../theme/colors'

type Props = {
  title?: string
  url: string
}

export default function LessonVideo({ title, url }: Props) {
  const { colors } = useTheme()
  const styles = useMemo(() => createStyles(colors), [colors])
  const player = useVideoPlayer({ uri: url, useCaching: true })

  return (
    <View style={styles.card}>
      <Text style={styles.eyebrow}>ВИДЕО К УРОКУ</Text>
      {!!title && <Text style={styles.title}>{title}</Text>}
      <VideoView
        accessibilityLabel={title || 'Видео к уроку'}
        contentFit="contain"
        fullscreenOptions={{ enable: true }}
        nativeControls
        player={player}
        playsInline
        style={styles.video}
      />
      <Text style={styles.hint}>Просмотр видео не меняет прогресс урока.</Text>
    </View>
  )
}

const createStyles = (colors: ThemeColors) => StyleSheet.create({
  card: {
    marginTop: 14,
    padding: 16,
    borderRadius: radius.card,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
  },
  eyebrow: { color: colors.gold, fontSize: 10, fontWeight: '900', letterSpacing: 0.9 },
  title: { color: colors.text, fontSize: 17, fontWeight: '800', lineHeight: 23, marginTop: 8 },
  video: { width: '100%', aspectRatio: 16 / 9, borderRadius: 12, marginTop: 12, backgroundColor: '#000' },
  hint: { color: colors.muted, fontSize: 11, lineHeight: 16, marginTop: 10 },
})
